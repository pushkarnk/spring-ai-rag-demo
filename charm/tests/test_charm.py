"""Smallest check of the relation -> env mapping. Run: PYTHONPATH=src:lib pytest tests"""

from ops import testing

from charm import RagAppCharm

LLM = testing.Relation("inference", remote_app_data={"url": "http://inf:8326/v1", "model": "glm"})
EMB = testing.Relation("embedding", remote_app_data={"url": "http://oll:11434", "model": "nomic-embed-text"})


def _db(endpoint, extra):
    secret = testing.Secret(tracked_content={"username": "u", "password": "p", **extra.pop("_secret", {})})
    rel = testing.Relation(endpoint, remote_app_data={"secret-user": secret.id, **extra})
    return rel, secret


def _run(*rels, secrets=()):
    ctx = testing.Context(RagAppCharm)
    state = testing.State(
        leader=True,
        containers={testing.Container("app", can_connect=True)},
        relations={LLM, EMB, *rels},
        secrets=set(secrets),
    )
    out = ctx.run(ctx.on.config_changed(), state)
    svc = out.get_container("app").layers.get("rag-app")
    return out, (svc.services["rag-app"].environment if svc else None)


def test_pgvector():
    pg, s = _db("postgresql", {"endpoints": "pg:5432", "database": "rag"})
    out, env = _run(pg, secrets=[s])
    assert out.unit_status == testing.ActiveStatus("pgvector + glm"), out.unit_status
    assert env["POSTGRES_URL"] == "jdbc:postgresql://pg:5432/rag"
    assert env["POSTGRES_PASSWORD"] == "p" and "SPRING_AUTOCONFIGURE_EXCLUDE" not in env
    assert env["INFERENCE_URL"] == "http://inf:8326/v1" and env["OLLAMA_URL"] == "http://oll:11434"


def test_opensearch():
    tls = testing.Secret(tracked_content={"tls-ca": "CERT"})
    os_, s = _db("opensearch", {"endpoints": "a:9200,b:9200", "index": "url-docs", "secret-tls": tls.id})
    out, env = _run(os_, secrets=[s, tls])
    assert out.unit_status == testing.ActiveStatus("opensearch + glm"), out.unit_status
    assert env["OPENSEARCH_URI"] == "https://a:9200,https://b:9200"
    assert env["SPRING_AUTOCONFIGURE_EXCLUDE"].endswith("DataSourceAutoConfiguration")
    assert env["SPRING_PROFILES_ACTIVE"] == "tls" and env["OPENSEARCH_CA_CERT"] == "/app/opensearch-ca.pem"


def test_vector_store_count():
    pg, s1 = _db("postgresql", {"endpoints": "pg:5432"})
    os_, s2 = _db("opensearch", {"endpoints": "a:9200"})
    out, env = _run(pg, os_, secrets=[s1, s2])
    assert out.unit_status == testing.BlockedStatus("integrate only one vector store") and env is None
    out, env = _run()
    assert out.unit_status == testing.BlockedStatus("integrate postgresql or opensearch") and env is None
