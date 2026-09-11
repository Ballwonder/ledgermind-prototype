
from dataclasses import asdict
from .data_model import SessionLocal,Transaction
from .transaction_enrichment import enrich_transaction
from .evidence_retrieval import retrieve_for_transaction
from .dual_autonomy_v034 import decide_dual

def process_transaction(hh:int,tx_id:int,facts=None):
    with SessionLocal() as s:
        tx=s.get(Transaction,tx_id)
        if not tx or tx.household_id!=hh: raise KeyError("transaction")
    enrichment=enrich_transaction(hh,tx_id,persist=True)
    try:
        retrieval=retrieve_for_transaction(hh,tx_id)
        retrieval_payload=retrieval.__dict__
    except Exception as e:
        retrieval_payload={"status":"unavailable","error":str(e)}
    with SessionLocal() as s:
        tx=s.get(Transaction,tx_id)
        decision=decide_dual(hh,tx,facts or {})
    return {
        "transaction_id":tx_id,
        "enrichment": enrichment if isinstance(enrichment,dict) else getattr(enrichment,"__dict__",str(enrichment)),
        "retrieval": retrieval_payload,
        "decision": asdict(decision)
    }

def process_all(hh:int,facts_by_tx=None):
    facts_by_tx=facts_by_tx or {}
    with SessionLocal() as s:
        ids=[x.id for x in s.query(Transaction).filter(Transaction.household_id==hh).order_by(Transaction.id).all()]
    results=[]
    for tid in ids:
        try: results.append(process_transaction(hh,tid,facts_by_tx.get(tid,{})))
        except Exception as e: results.append({"transaction_id":tid,"error":str(e)})
    return results
