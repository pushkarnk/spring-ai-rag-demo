#!/usr/bin/env python3
"""rag-app: relations -> env vars -> Pebble -> Spring Boot. Restarts on any change."""

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires, OpenSearchRequires

CA_PATH = "/app/opensearch-ca.pem"
NO_JDBC = "org.springframework.boot.jdbc.autoconfigure.DataSourceAutoConfiguration"


class RagAppCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        self.pg = DatabaseRequires(self, "postgresql", database_name="rag")
        # ponytail: admin so initialize-schema can create the index; narrow if the default role suffices.
        self.os = OpenSearchRequires(self, "opensearch", index="url-docs", extra_user_roles="admin")
        for e in (
            self.on.app_pebble_ready, self.on.config_changed, self.on.upgrade_charm,
            self.pg.on.database_created, self.pg.on.endpoints_changed,
            self.os.on.index_created, self.os.on.authentication_updated,
            self.on.postgresql_relation_broken, self.on.opensearch_relation_broken,
            self.on.inference_relation_changed, self.on.inference_relation_broken,
            self.on.embedding_relation_changed, self.on.embedding_relation_broken,
        ):
            framework.observe(e, self._reconcile)

    def _reconcile(self, event):
        c = self.unit.get_container("app")
        if not c.can_connect():
            return self._status(ops.WaitingStatus("waiting for Pebble"))

        inf, emb = self._remote("inference", event), self._remote("embedding", event)
        if not inf.get("url"):
            return self._status(ops.BlockedStatus("integrate an inference charm"))
        if not emb.get("url"):
            return self._status(ops.BlockedStatus("integrate an embedding (ollama) charm"))

        pg, os_ = self._live("postgresql", event), self._live("opensearch", event)
        if pg and os_:
            return self._status(ops.BlockedStatus("integrate only one vector store"))
        if not (pg or os_):
            return self._status(ops.BlockedStatus("integrate postgresql or opensearch"))

        env = {
            "INFERENCE_URL": inf["url"],
            "INFERENCE_MODEL": inf.get("model", ""),
            "OLLAMA_URL": emb["url"],
            "OLLAMA_MODEL": emb.get("model", "nomic-embed-text"),
            "RAG_TOP_K": str(self.config["top-k"]),
            "RAG_CHUNK_SIZE": str(self.config["chunk-size"]),
        }
        if pg:
            d = self.pg.fetch_relation_data().get(pg.id, {})
            if not (d.get("password") and d.get("endpoints")):
                return self._status(ops.WaitingStatus("waiting for postgresql credentials"))
            env |= {
                "VECTORSTORE_TYPE": "pgvector",
                "POSTGRES_URL": f"jdbc:postgresql://{d['endpoints'].split(',')[0]}/{d.get('database', 'rag')}",
                "POSTGRES_USERNAME": d["username"],
                "POSTGRES_PASSWORD": d["password"],
            }
        else:
            d = self.os.fetch_relation_data().get(os_.id, {})
            if not (d.get("password") and d.get("endpoints")):
                return self._status(ops.WaitingStatus("waiting for opensearch credentials"))
            env |= {
                "VECTORSTORE_TYPE": "opensearch",
                "SPRING_AUTOCONFIGURE_EXCLUDE": NO_JDBC,
                "OPENSEARCH_URI": ",".join(f"https://{e}" for e in d["endpoints"].split(",")),
                "OPENSEARCH_USERNAME": d["username"],
                "OPENSEARCH_PASSWORD": d["password"],
                "OPENSEARCH_INDEX": d.get("index", "url-docs"),
            }
            if d.get("tls-ca"):
                c.push(CA_PATH, d["tls-ca"], make_dirs=True)
                env |= {"SPRING_PROFILES_ACTIVE": "tls", "OPENSEARCH_CA_CERT": CA_PATH}

        c.add_layer("rag-app", {
            "services": {"rag-app": {
                "override": "replace",
                "startup": "enabled",
                "command": "java -jar /app/app.jar",
                "environment": env,
            }},
        }, combine=True)
        c.replan()  # Pebble restarts the service only if the layer changed
        self.unit.set_ports(8080)
        self._status(ops.ActiveStatus(f"{env['VECTORSTORE_TYPE']} + {env['INFERENCE_MODEL']}"))

    def _live(self, name, event):
        """The relation, unless it is the one being broken right now."""
        rel = self.model.get_relation(name)
        if rel and isinstance(event, ops.RelationBrokenEvent) and event.relation.id == rel.id:
            return None
        return rel

    def _remote(self, name, event):
        rel = self._live(name, event)
        return dict(rel.data[rel.app]) if rel and rel.app else {}

    def _status(self, status):
        self.unit.status = status


if __name__ == "__main__":
    ops.main(RagAppCharm)
