import os
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import ChatPromptTemplate

# 0. Get the query first to decide which documents to load
query = input("Ask a question: ") or "What is this document about?"
print(f"Query: {query}")

# 1. Find and filter documents in the data folder based on the query
data_dir = "data"
supported_extensions = (".docx", ".pdf")
all_files = [f for f in os.listdir(data_dir) if f.lower().endswith(supported_extensions)]

if not all_files:
    print(f"Error: No supported documents found in {data_dir}.")
    exit(1)

# Logic to filter based on query keywords
query_lower = query.lower()
if "pdf" in query_lower and "docx" not in query_lower and "word" not in query_lower:
    files_to_load = [f for f in all_files if f.lower().endswith(".pdf")]
    print("Routing to PDF files only...")
elif ("docx" in query_lower or "word" in query_lower) and "pdf" not in query_lower:
    files_to_load = [f for f in all_files if f.lower().endswith(".docx")]
    print("Routing to DOCX files only...")
else:
    files_to_load = all_files
    print("Studying all available documents...")

if not files_to_load:
    print("No matching files found for your query. Studying everything instead.")
    files_to_load = all_files

# 2. Load the filtered documents
docs = []
for file_name in files_to_load:
    file_path = os.path.join(data_dir, file_name)
    print(f"Loading: {file_path}")
    if file_name.lower().endswith(".docx"):
        loader = Docx2txtLoader(file_path)
    elif file_name.lower().endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    docs.extend(loader.load())

if not docs:
    print("Failed to load any documents.")
    exit(1)

# 3. Split the document into chunks
print("\nChunking Options:")
print("1. Recursive Character Splitting (Recommended)")
print("2. Fixed Size Character Splitting")
chunk_choice = "1" 

if chunk_choice == "1":
    print("Using Recursive Character Splitting...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
else:
    from langchain_text_splitters import CharacterTextSplitter
    print("Using Fixed Size Character Splitting...")
    splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=0)

chunks = splitter.split_documents(docs)
print(f"Created {len(chunks)} chunks.")

# 4. Create Embeddings and Vector Store
print("Initializing embeddings (nomic-embed-text) and vector store...")
embedding = OllamaEmbeddings(model="nomic-embed-text")

persist_directory = "./chroma_db"
if os.path.exists(persist_directory):
    import shutil
    shutil.rmtree(persist_directory)

vector_db = Chroma.from_documents(
    documents=chunks,
    embedding=embedding,
    persist_directory=persist_directory
)

# 5. Setup Retriever
retriever = vector_db.as_retriever(search_kwargs={"k": 3})

# 6. Initialize LLM
print("Initializing LLM (tinyllama)...")
llm = OllamaLLM(model="tinyllama")

# 7. Create QA Chain (Using classic RetrievalQA)
print("Creating QA Chain...")
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever
)

# 8. Run the query
print(f"\nFinal Query: {query}")
response = qa_chain.run(query)

print("\nResponse:")
print(response)



