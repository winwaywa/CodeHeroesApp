from anyio import Path
from retriever.pinecone.rule.rule_retriever import PineconeRuleRetriever


INDEX_NAME = "code-rules"
FILE_PATH = str(Path(__file__).with_name("python_rule_01.txt")) 
LANGUAGE="python"

def main():
    retriever = PineconeRuleRetriever(index_name=INDEX_NAME)
    count = retriever.import_rules_from_txt(
        file_path=FILE_PATH,
        language=LANGUAGE
    )
    print(f"✅ Imported {count} chunks from '{FILE_PATH}' into index '{INDEX_NAME}' (lang={LANGUAGE}).")


if __name__ == "__main__":
    main()


# Usage:
# PYTHONPATH=. python3 tmp/script/run_import.py