import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from typing import List

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "data"
CHROMA_DIR = "./chroma_db"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Global vector_db reference
_vector_db = None
_current_state_signature = ""

def get_data_state_signature():
    """Generates a unique signature based on file names, sizes, and modification times."""
    supported_extensions = (".docx", ".pdf")
    files = sorted([f for f in os.listdir(DATA_DIR) if f.lower().endswith(supported_extensions)])
    sig_parts = []
    for f in files:
        path = os.path.join(DATA_DIR, f)
        stats = os.stat(path)
        sig_parts.append(f"{f}:{stats.st_size}:{stats.st_mtime}")
    return "|".join(sig_parts)

def get_vector_db():
    global _vector_db, _current_state_signature
    
    new_sig = get_data_state_signature()
    
    # If no files, clear everything and return None
    if not new_sig:
        if _vector_db:
            print("No files found. Clearing vector database.")
            _vector_db = None
            if os.path.exists(CHROMA_DIR):
                shutil.rmtree(CHROMA_DIR, ignore_errors=True)
        _current_state_signature = ""
        return None

    # If state hasn't changed, return existing DB
    if _vector_db is not None and new_sig == _current_state_signature:
        print("Data state unchanged. Using cached vector database.")
        return _vector_db

    print(f"Detected change in data folder. Refreshing vector database...")
    print(f"Current Signature: {new_sig}")
    
    # Explicitly clear old DB reference to release file handles
    _vector_db = None
    
    if os.path.exists(CHROMA_DIR):
        print(f"Wiping old index at {CHROMA_DIR}")
        shutil.rmtree(CHROMA_DIR, ignore_errors=True)

    supported_extensions = (".docx", ".pdf")
    current_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(supported_extensions)]
    
    docs = []
    for file_name in current_files:
        file_path = os.path.join(DATA_DIR, file_name)
        try:
            if file_name.lower().endswith(".docx"):
                loader = Docx2txtLoader(file_path)
            elif file_name.lower().endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            loaded_docs = loader.load()
            print(f" -> Loaded {len(loaded_docs)} pages from {file_name}")
            docs.extend(loaded_docs)
        except Exception as e:
            print(f" !! Error loading {file_name}: {e}")

    if not docs:
        print(" !! No documents were successfully loaded.")
        return None

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(docs)
    print(f" -> Created {len(chunks)} chunks total.")

    if not chunks:
        return None

    embedding = OllamaEmbeddings(model="nomic-embed-text")
    
    try:
        _vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=embedding,
            persist_directory=CHROMA_DIR
        )
        _current_state_signature = new_sig
        print("Successfully re-indexed all documents.")
    except Exception as e:
        print(f" !! Error creating vector database: {e}")
        return None
        
    return _vector_db

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(DATA_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename, "status": "success"}

@app.get("/files")
async def list_files():
    supported_extensions = (".docx", ".pdf")
    files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(supported_extensions)]
    return {"files": files}

@app.delete("/delete/{filename}")
async def delete_file(filename: str):
    file_path = os.path.join(DATA_DIR, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"File deleted: {filename}")
            return {"status": "success", "message": f"File {filename} deleted."}
        except Exception as e:
            return {"status": "error", "message": f"Error deleting file: {e}"}
    return {"status": "error", "message": "File not found."}

def detect_intent(question: str):
    # Layer 1: Hard-coded Keyword Filter (Fail-safe)
    harmful_keywords = [
        "bomb", "explosive", "nuclear", "weapon", "kill", "murder", 
        "hack", "attack", "illegal", "drug", "poison", "toxic", "harm"
    ]
    query_lower = question.lower()
    if any(word in query_lower for word in harmful_keywords):
        print(f" -> Safety Trigger: Found harmful keyword.")
        return "UNSAFE"

    # Layer 2: LLM Classification (Simple)
    llm = OllamaLLM(model="tinyllama")
    
    prompt = f"""
    Categorize the following text into exactly ONE of these four categories:
    1. GREETING (Examples: hi, hello, good morning)
    2. OFF_TOPIC (Examples: tell me a joke, who is the president, what is python)
    3. UNSAFE (Examples: how to steal, bad words)
    4. DOCUMENT_QUESTION (Examples: summarize the file, what does the page say, what is the certificate for)

    Text to categorize: "{question}"
    
    Reply with ONLY the category name. Do not say anything else.
    Category:"""
    
    try:
        category = llm.invoke(prompt).strip().upper()
        print(f" -> Guardrail Intent Detection: {category}")
        
        if "UNSAFE" in category: return "UNSAFE"
        if "GREETING" in category: return "GREETING"
        if "OFF" in category or "TOPIC" in category: return "OFF_TOPIC"
        return "DOCUMENT_QUESTION"
    except Exception as e:
        print(f" !! Intent detection failed: {e}")
        return "DOCUMENT_QUESTION"

@app.post("/ask")
async def ask_question(question: str = Form(...)):
    intent = detect_intent(question)
    print(f"Detected intent: {intent}")

    if intent == "UNSAFE":
        return {"answer": "I'm sorry, but I cannot answer harmful or inappropriate questions.", "status": "unsafe"}
    
    if intent == "OFF_TOPIC":
        return {"answer": "I am specifically designed to help you with your uploaded documents. I cannot answer questions about other topics.", "status": "off_topic"}
    
    if intent == "GREETING":
        return {"answer": "Hello! I'm your DocQHub assistant. How can I help you with your documents today?", "status": "greeting"}

    vdb = get_vector_db()
    if not vdb:
        return {"answer": "No documents found. Please upload some files first.", "status": "no_docs"}

    retriever = vdb.as_retriever(search_kwargs={"k": 3})
    llm = OllamaLLM(model="tinyllama")
    
    # Restrictive Prompt
    system_prompt = """You are a helpful assistant for document Q-A. 
    Use the following pieces of retrieved context to answer the user's question. 
    If the answer is not in the context, say that you don't know based on the provided documents. 
    Do not use outside knowledge.
    
    Context: {context}
    Question: {question}
    Answer:"""
    
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm, 
        retriever=retriever,
        chain_type_kwargs={"prompt": ChatPromptTemplate.from_template(system_prompt)}
    )
    
    response = qa_chain.invoke(question)
    return {"answer": response["result"], "status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
