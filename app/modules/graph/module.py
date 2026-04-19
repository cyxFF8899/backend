from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from neo4j import GraphDatabase, Session

from ...config import Settings


class GraphModule:
    """图数据模块（独立于 RAG）。

    提供 Neo4j 图数据库的基本操作。
    """

    def __init__(self, settings: Settings, project_root: Path) -> None:
        self.settings = settings
        self.project_root = project_root
        self.driver = None
        self._connect()

    def _connect(self) -> None:
        """连接到 Neo4j 数据库。"""
        try:
            self.driver = GraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_username, self.settings.neo4j_password)
            )
            # 测试连接
            with self.driver.session() as session:
                session.run("MATCH (n) RETURN count(n) AS count")
        except Exception as e:
            print(f"Neo4j 连接失败: {e}")
            self.driver = None

    def _get_session(self) -> Optional[Session]:
        """获取数据库会话。"""
        if not self.driver:
            self._connect()
        if self.driver:
            return self.driver.session()
        return None

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """搜索图数据库。

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            搜索结果列表
        """
        session = self._get_session()
        if not session:
            return []

        try:
            # 简单的全文搜索示例
            keyword = str(query or "").strip()
            cypher_query = """
            MATCH (n) 
            WHERE n.name CONTAINS $keyword OR n.description CONTAINS $keyword
            RETURN n LIMIT $limit
            """
            result = session.run(cypher_query, keyword=keyword, limit=limit)
            return [record["n"]._properties for record in result]
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
        finally:
            session.close()

    def create_node(self, label: str, properties: dict[str, Any]) -> dict[str, Any]:
        """创建节点。

        Args:
            label: 节点标签
            properties: 节点属性

        Returns:
            创建的节点属性
        """
        session = self._get_session()
        if not session:
            return {}

        try:
            # 构建属性字符串
            props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()])
            cypher_query = f"CREATE (n:{label} {{ {props_str} }}) RETURN n"
            result = session.run(cypher_query, **properties)
            return result.single()["n"]._properties
        except Exception as e:
            print(f"创建节点失败: {e}")
            return {}
        finally:
            session.close()

    def create_relationship(self, start_id: str, end_id: str, relationship_type: str, properties: dict[str, Any] = None) -> bool:
        """创建关系。

        Args:
            start_id: 起始节点ID
            end_id: 结束节点ID
            relationship_type: 关系类型
            properties: 关系属性

        Returns:
            是否创建成功
        """
        session = self._get_session()
        if not session:
            return False

        try:
            if properties:
                props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()])
                cypher_query = f"""
                MATCH (a), (b)
                WHERE a.id = $start_id AND b.id = $end_id
                CREATE (a)-[r:{relationship_type} {{ {props_str} }}]->(b)
                RETURN r
                """
                session.run(cypher_query, start_id=start_id, end_id=end_id, **properties)
            else:
                cypher_query = f"""
                MATCH (a), (b)
                WHERE a.id = $start_id AND b.id = $end_id
                CREATE (a)-[r:{relationship_type}]->(b)
                RETURN r
                """
                session.run(cypher_query, start_id=start_id, end_id=end_id)
            return True
        except Exception as e:
            print(f"创建关系失败: {e}")
            return False
        finally:
            session.close()

    def get_node_by_id(self, node_id: str) -> dict[str, Any]:
        """根据ID获取节点。

        Args:
            node_id: 节点ID

        Returns:
            节点属性
        """
        session = self._get_session()
        if not session:
            return {}

        try:
            cypher_query = """
            MATCH (n) 
            WHERE n.id = $node_id
            RETURN n
            """
            result = session.run(cypher_query, node_id=node_id)
            record = result.single()
            return record["n"]._properties if record else {}
        except Exception as e:
            print(f"获取节点失败: {e}")
            return {}
        finally:
            session.close()

    def get_relationships(self, node_id: str) -> list[dict[str, Any]]:
        """获取节点的所有关系。

        Args:
            node_id: 节点ID

        Returns:
            关系列表
        """
        session = self._get_session()
        if not session:
            return []

        try:
            cypher_query = """
            MATCH (a)-[r]->(b) 
            WHERE a.id = $node_id
            RETURN type(r) AS type, b.id AS target_id, b.name AS target_name, r
            """
            result = session.run(cypher_query, node_id=node_id)
            return [{
                "type": record["type"],
                "target_id": record["target_id"],
                "target_name": record["target_name"],
                "properties": record["r"]._properties
            } for record in result]
        except Exception as e:
            print(f"获取关系失败: {e}")
            return []
        finally:
            session.close()

    def close(self) -> None:
        """关闭数据库连接。"""
        if self.driver:
            self.driver.close()

    def get_stats(self) -> dict[str, Any]:
        """获取图谱统计信息。"""
        session = self._get_session()
        if not session:
            return {"node_count": 0, "relationship_count": 0, "labels": []}

        try:
            node_count_query = "MATCH (n) RETURN count(n) AS count"
            rel_count_query = "MATCH ()-[r]->() RETURN count(r) AS count"
            labels_query = "CALL db.labels() YIELD label RETURN label"

            node_result = session.run(node_count_query)
            rel_result = session.run(rel_count_query)
            labels_result = session.run(labels_query)

            node_count = node_result.single()["count"] if node_result.peek() else 0
            rel_count = rel_result.single()["count"] if rel_result.peek() else 0
            labels = [record["label"] for record in labels_result]

            return {
                "node_count": node_count,
                "relationship_count": rel_count,
                "labels": labels
            }
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {"node_count": 0, "relationship_count": 0, "labels": []}
        finally:
            session.close()

    def get_labels(self) -> dict[str, int]:
        """获取所有节点标签及其数量。"""
        session = self._get_session()
        if not session:
            return {}

        try:
            cypher_query = """
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN label, count(*) AS count ORDER BY count DESC
            """
            result = session.run(cypher_query)
            label_counts = {record["label"]: record["count"] for record in result}
            return label_counts
        except Exception as e:
            print(f"获取标签失败: {e}")
            return {}
        finally:
            session.close()

    def get_nodes(self, label: str = None, keyword: str = None, limit: int = 100) -> list[dict[str, Any]]:
        """获取节点列表。

        Args:
            label: 节点标签过滤
            keyword: 关键词搜索
            limit: 返回数量限制

        Returns:
            节点列表
        """
        session = self._get_session()
        if not session:
            return []

        try:
            if label:
                if keyword:
                    cypher_query = """
                    MATCH (n:%s)
                    WHERE n.name CONTAINS $keyword OR n.description CONTAINS $keyword
                    RETURN n, elementId(n) AS eid LIMIT $limit
                    """ % label
                    result = session.run(cypher_query, keyword=keyword, limit=limit)
                else:
                    cypher_query = """
                    MATCH (n:%s)
                    RETURN n, elementId(n) AS eid LIMIT $limit
                    """ % label
                    result = session.run(cypher_query, limit=limit)
            elif keyword:
                cypher_query = """
                MATCH (n)
                WHERE n.name CONTAINS $keyword OR n.description CONTAINS $keyword
                RETURN n, elementId(n) AS eid LIMIT $limit
                """
                result = session.run(cypher_query, keyword=keyword, limit=limit)
            else:
                cypher_query = """
                MATCH (n)
                RETURN n, elementId(n) AS eid LIMIT $limit
                """
                result = session.run(cypher_query, limit=limit)

            nodes = []
            for record in result:
                node = record["n"]
                eid = record["eid"]
                props = node._properties
                node_data = {
                    **props,
                    "_id": eid,
                    "_labels": list(node.labels),
                    "id": eid,
                    "labels": list(node.labels),
                    "name": props.get("name", props.get("名称", "")),
                }
                nodes.append(node_data)
            return nodes
        except Exception as e:
            print(f"获取节点失败: {e}")
            return []
        finally:
            session.close()

    def get_subgraph(self, depth: int = 1, limit: int = 80, keyword: str = None, label: str = None, node_ids: list[str] = None) -> dict[str, Any]:
        """获取子图数据（用于可视化）。

        Args:
            depth: 子图展开深度
            limit: 节点数量限制
            keyword: 关键词搜索
            label: 节点标签过滤
            node_ids: 指定节点ID列表

        Returns:
            包含节点和关系的子图数据
        """
        session = self._get_session()
        if not session:
            return {"nodes": [], "edges": []}

        try:
            if node_ids:
                node_query = """
                MATCH (n)
                WHERE elementId(n) IN $node_ids
                RETURN n, elementId(n) AS eid
                """
                result = session.run(node_query, node_ids=node_ids)
            elif label:
                if keyword:
                    node_query = f"""
                    MATCH (n:{label})
                    WHERE n.name CONTAINS $keyword OR n.description CONTAINS $keyword
                    RETURN n, elementId(n) AS eid LIMIT $limit
                    """
                    result = session.run(node_query, keyword=keyword, limit=limit)
                else:
                    node_query = f"""
                    MATCH (n:{label})
                    RETURN n, elementId(n) AS eid LIMIT $limit
                    """
                    result = session.run(node_query, limit=limit)
            elif keyword:
                node_query = """
                MATCH (n)
                WHERE n.name CONTAINS $keyword OR n.description CONTAINS $keyword
                RETURN n, elementId(n) AS eid LIMIT $limit
                """
                result = session.run(node_query, keyword=keyword, limit=limit)
            else:
                node_query = """
                MATCH (n)
                RETURN n, elementId(n) AS eid LIMIT $limit
                """
                result = session.run(node_query, limit=limit)

            nodes = []
            for record in result:
                node = record["n"]
                eid = record["eid"]
                props = node._properties
                node_data = {
                    **props,
                    "_id": eid,
                    "_labels": list(node.labels),
                    "id": eid,
                    "labels": list(node.labels),
                    "name": props.get("name", props.get("名称", "")),
                }
                nodes.append(node_data)

            if not nodes:
                return {"nodes": [], "edges": []}

            node_eids = [n["id"] for n in nodes]
            node_eid_set = set(node_eids)

            rel_query = """
            MATCH (a)-[r]->(b)
            WHERE elementId(a) IN $node_ids
            RETURN elementId(a) AS source, elementId(b) AS target, type(r) AS type, properties(r) AS properties, b, elementId(b) AS b_eid
            LIMIT 200
            """
            rel_result = session.run(rel_query, node_ids=node_eids)

            edges = []
            for record in rel_result:
                target_eid = record["b_eid"]
                if target_eid not in node_eid_set:
                    target_node = record["b"]
                    target_props = target_node._properties
                    target_data = {
                        **target_props,
                        "_id": target_eid,
                        "_labels": list(target_node.labels),
                        "id": target_eid,
                        "labels": list(target_node.labels),
                        "name": target_props.get("name", target_props.get("名称", "")),
                    }
                    nodes.append(target_data)
                    node_eid_set.add(target_eid)

                edges.append({
                    "source": record["source"],
                    "target": record["target"],
                    "type": record["type"],
                    "properties": record["properties"] if record["properties"] else {}
                })

            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            print(f"获取子图失败: {e}")
            return {"nodes": [], "edges": []}
        finally:
            session.close()

    def get_node_relationships(self, node_id: str) -> list[dict[str, Any]]:
        """获取节点的所有关系。

        Args:
            node_id: 节点ID（element_id）

        Returns:
            关系列表
        """
        session = self._get_session()
        if not session:
            return []

        try:
            cypher_query = """
            MATCH (a)-[r]->(b)
            WHERE elementId(a) = $node_id
            RETURN elementId(a) AS source_id, elementId(b) AS target_id, b.name AS target_name, type(r) AS type, properties(r) AS properties
            """
            result = session.run(cypher_query, node_id=node_id)

            relationships = []
            for record in result:
                relationships.append({
                    "rel_type": record["type"],
                    "source_id": record["source_id"],
                    "target_id": record["target_id"],
                    "target_name": record["target_name"],
                    "direction": "outgoing",
                    "type": record["type"],
                    "properties": record["properties"] if record["properties"] else {}
                })

            if not relationships:
                cypher_query2 = """
                MATCH (a)<-[r]-(b)
                WHERE elementId(a) = $node_id
                RETURN elementId(b) AS source_id, elementId(a) AS target_id, b.name AS target_name, type(r) AS type, properties(r) AS properties
                """
                result2 = session.run(cypher_query2, node_id=node_id)
                for record in result2:
                    relationships.append({
                        "rel_type": record["type"],
                        "source_id": record["source_id"],
                        "target_id": record["target_id"],
                        "target_name": record["target_name"],
                        "direction": "incoming",
                        "type": record["type"],
                        "properties": record["properties"] if record["properties"] else {}
                    })

            return relationships
        except Exception as e:
            print(f"获取节点关系失败: {e}")
            return []
        finally:
            session.close()
