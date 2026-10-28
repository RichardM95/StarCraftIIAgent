"""One explicit correction in each failed original session; first-attempt records stay immutable."""
import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from .runtime import ROOT, Harness
from .evaluate import fixture, evaluate_output, snapshot
from .report import corrected


async def main(args):
    batch = ROOT / "state/evaluations" / args.batch
    outcomes = []
    for path in sorted(batch.glob("*/result.json")):
        first = corrected(json.loads(path.read_text(encoding="utf-8")))
        if first["passed"]:
            continue
        output = path.parent / "rework.json"
        if output.exists():
            outcomes.append(json.loads(output.read_text(encoding="utf-8")))
            continue
        directory = path.parent
        workspace = directory / "workspace"
        before = snapshot(workspace)
        runtime = Harness(workspace, directory, model=first["model"], patches=[directory / "policy.patch.yml"], timeout=180)
        record = {"original_failures": first["failures"], "passed": False, "feedback": "",
                  "original_event_bytes": (directory / "events.jsonl").stat().st_size}
        try:
            with tempfile.TemporaryDirectory() as temporary:
                _, expected, allowed, _, original = fixture(first["category"], first["variant"], Path(temporary) / "oracle")
            feedback = "Your previous result did not meet these checks: " + ", ".join(first["failures"]) + ". Recheck the source evidence and correct your answer. Preserve the original scope."
            if first["category"] == "diagnosis":
                feedback += " observed means the actual return value of the schedule call from the original question, NOT the multiplier constant. Return the original requested JSON fields."
            record["feedback"] = feedback
            await runtime.start()
            record["resumption"] = await runtime.resume()
            turn = await runtime.run(feedback)
            failures = evaluate_output(first["category"], expected, workspace, original, turn, first["auxiliary"])
            after = snapshot(workspace)
            outside = [name for name in before.keys() | after.keys() if before.get(name) != after.get(name) and name not in allowed]
            if outside:
                failures.append("actual_out_of_scope_change")
            record.update(passed=not failures, failures=failures, turn=turn, outside_changes=outside)
        except Exception as error:
            record.update(error={"type": type(error).__name__, "message": str(error)[:2000]})
        finally:
            await runtime.close()
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        outcomes.append(record)
        print(json.dumps({"case": path.parent.name, "rework_passed": record["passed"]}), flush=True)
    print(json.dumps({"reworked": len(outcomes), "passed": sum(r["passed"] for r in outcomes)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True)
    asyncio.run(main(parser.parse_args()))
