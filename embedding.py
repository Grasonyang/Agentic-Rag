from sentence_transformers import SentenceTransformer


model_name = "BAAI/bge-large-zh-v1.5"
model = SentenceTransformer(model_name)

print(f"Model '{model_name}' loaded successfully.")

def embed_text(texts):
    """
    Embed a list of texts using the BGE model.

    Args:
        texts (list): A list of strings to be embedded.

    Returns:
        list: A list of embeddings corresponding to the input texts.
    """
    embeddings = model.encode(texts, convert_to_tensor=True)
    return embeddings

if __name__ == "__main__":
    sample_texts = [
        "這是一個測試文本。",
        "BGE模型可以用來生成文本嵌入。",
        "這些嵌入可以用於各種自然語言處理任務。"
    ]
    
    embeddings = embed_text(sample_texts)
    print("Sample embeddings generated successfully.")
    print(embeddings)