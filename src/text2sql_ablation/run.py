"""Main loop: for each question x config, generate SQL, execute, compare, log."""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from tqdm import tqdm

from .comparator import has_order_by, results_match
from .context import build_prompt
from .llm import generate_sql, make_client


def execute(db_path: Path, sql: str, timeout_s: float = 30.0):
    conn = sqlite3.connect(db_path)
    deadline = time.time() + timeout_s
    conn.set_progress_handler(lambda: int(time.time() > deadline), 10_000)
    try:
        return conn.execute(sql).fetchall(), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"
    finally:
        conn.close()


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/experiment.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())

    bird = Path(cfg["data"]["bird_dir"])
    questions = json.loads((bird / cfg["data"]["questions_file"]).read_text())
    if cfg["data"]["db_ids"]:
        questions = [q for q in questions if q["db_id"] in cfg["data"]["db_ids"]]
    questions = questions[: cfg["data"]["max_questions"]]

    client = make_client()
    out_dir = Path(cfg["output_dir"]) / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "results.jsonl"

    with out_file.open("w") as f:
        for qi, q in enumerate(tqdm(questions)):
            db_dir = bird / "dev_databases" / q["db_id"]
            db_path = db_dir / f"{q['db_id']}.sqlite"
            gold_rows, gold_err = execute(db_path, q["SQL"])
            if gold_err:
                continue
            for config in cfg["configs"]:
                for s in range(cfg["samples_per_question"]):
                    prompt = build_prompt(config, q, db_dir, client=client, model=cfg["model"])
                    pred_sql = generate_sql(client, cfg["model"], prompt, cfg["temperature"])
                    pred_rows, pred_err = execute(db_path, pred_sql)
                    correct = pred_err is None and results_match(
                        gold_rows, pred_rows, ordered=has_order_by(q["SQL"])
                    )
                    f.write(json.dumps({
                        "qid": qi, "db_id": q["db_id"], "difficulty": q.get("difficulty"),
                        "config": config, "sample": s, "pred_sql": pred_sql,
                        "error": pred_err, "correct": correct,
                    }) + "\n")

    print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
