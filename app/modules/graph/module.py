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
