import os
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_ollama import ChatOllama
from langchain_neo4j import GraphCypherQAChain   # 修改处

load_dotenv()

graph = Neo4jGraph(
    url="bolt://localhost:7687",
    username="neo4j",
    password=os.getenv("NEO4J_PASSWORD"),
    database="neo4j"
)

llm = ChatOllama(
    model="llama3",
    temperature=0,
)

chain = GraphCypherQAChain.from_llm(
    graph=graph,
    cypher_llm=llm,
    qa_llm=llm,
    allow_dangerous_requests=True,
    verbose=True,
    return_direct=False,
    top_k=10
)

if __name__ == "__main__":
    print("地图知识图谱智能体已启动（使用 Ollama 本地模型）")
    while True:
        question = input("\n问题: ")
        if question.lower() in ['退出', 'exit', 'quit']:
            break
        try:
            result = chain.invoke(question)
            print("\n回答:", result['result'])
        except Exception as e:
            print(f"出错了: {e}")