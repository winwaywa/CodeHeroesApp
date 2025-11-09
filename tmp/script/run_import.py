from anyio import Path
from retriever.pinecone.rule.rule_retriever import PineconeRuleRetriever


INDEX_NAME = "code-rules"
FILE_NAME= "python_rule.txt"
LANGUAGE="python"
FILE_PATH = str(Path(__file__).with_name(FILE_NAME)) 

def main():
    retriever = PineconeRuleRetriever(index_name=INDEX_NAME)
    count = retriever.import_rules_from_txt(
        file_path=FILE_PATH,
        language=LANGUAGE,
        source_path=FILE_NAME
    )
    print(f"✅ Imported {count} chunks from '{FILE_PATH}' into index '{INDEX_NAME}' (lang={LANGUAGE}).")


if __name__ == "__main__":
    main()


# Usage:
# PYTHONPATH=. python3 tmp/script/run_import.py