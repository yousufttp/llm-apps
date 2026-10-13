import sqlite3
from database import get_connection, utc_now


def remediate_issue(*, run_id, incident_id, root_cause, idempotency_key):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT status,message FROM tira_remediation_operations WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if row:
            return {
                "status": row["status"],
                "message": f"Already processed: {row['message']}",
                "duplicate": True,
            }
        if root_cause == "switch_provisioning_mismatch":
            message = "Switch provisioning reset completed"
        elif root_cause == "clnr_limit_error":
            message = "CLNR remediation completed"
        else:
            return {
                "status": "failed",
                "message": "No supported remediation for root cause",
                "duplicate": False,
            }
        try:
            conn.execute(
                "INSERT INTO tira_remediation_operations(idempotency_key,run_id,incident_id,root_cause,status,message,created_at) VALUES(?,?,?,?, 'success', ?,?)",
                (idempotency_key, run_id, incident_id, root_cause, message, utc_now()),
            )
        except sqlite3.IntegrityError:
            row = conn.execute(
                "SELECT status,message FROM tira_remediation_operations WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            return {
                "status": row["status"],
                "message": f"Already processed: {row['message']}",
                "duplicate": True,
            }
        return {"status": "success", "message": message, "duplicate": False}
