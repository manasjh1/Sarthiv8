import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from .keywords import red_list, yellow_list
from config import AppConfig

# Load environment variables from .env file
load_dotenv()

def populate_pinecone():
    """
    Connects to OpenAI and Pinecone to populate the distress detection index.
    """
    print("🚀 Starting Pinecone population script...")
    
    # Load configuration from the central AppConfig
    try:
        app_config = AppConfig.from_env()
        pinecone_config = app_config.distress
        openai_key = app_config.llm.api_key
        embed_model = pinecone_config.openai_embed_model
        index_name = pinecone_config.pinecone_index
        namespace = pinecone_config.pinecone_namespace
        
        print(f"✅ Configuration loaded successfully.")
        print(f"   - Pinecone Index: {index_name}")
        print(f"   - Embedding Model: {embed_model}")

    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return

    # Initialize clients
    openai_client = OpenAI(api_key=openai_key)
    pc = Pinecone(api_key=pinecone_config.pinecone_api_key)

    # Check if the index exists, create it if not
    if index_name not in [index.name for index in pc.list_indexes()]:
        print(f"Index '{index_name}' not found. Creating a new one...")
        pc.create_index(
            name=index_name,
            dimension=1536,  # Based on text-embedding-3-small
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        print(f"✅ Index '{index_name}' created successfully.")
    
    index = pc.Index(index_name)

    def get_embeddings(text_list, model):
        response = openai_client.embeddings.create(model=model, input=text_list)
        return [item.embedding for item in response.data]

    # Upload red list
    print("\nProcessing and uploading red (critical) keywords...")
    red_embeddings = get_embeddings(red_list, embed_model)
    red_vectors = list(zip(
        [f"red_{i}" for i in range(len(red_list))],
        red_embeddings,
        [{"category": "red", "text": t} for t in red_list]
    ))
    index.upsert(vectors=red_vectors, namespace=namespace)
    print(f"✅ Uploaded {len(red_vectors)} red keywords.")

    # Upload yellow list
    print("\nProcessing and uploading yellow (warning) keywords...")
    yellow_embeddings = get_embeddings(yellow_list, embed_model)
    yellow_vectors = list(zip(
        [f"yellow_{i}" for i in range(len(yellow_list))],
        yellow_embeddings,
        [{"category": "yellow", "text": t} for t in yellow_list]
    ))
    index.upsert(vectors=yellow_vectors, namespace=namespace)
    print(f"✅ Uploaded {len(yellow_vectors)} yellow keywords.")
    
    print("\n🎉 Pinecone population complete!")

if __name__ == "__main__":
    populate_pinecone()