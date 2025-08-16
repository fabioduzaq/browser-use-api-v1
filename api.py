import asyncio
import os
import sys
from typing import Dict, Optional
from datetime import datetime
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Browser Agent API",
    description="API REST para automação de navegador usando LangChain e Browser-Use",
    version="1.0.0"
)

# Initialize the model
llm = ChatOpenAI(
    model='gpt-4o',
    temperature=0.0,
)

# Store for tracking tasks
tasks_store: Dict[str, Dict] = {}

# Pydantic models for request/response
class TaskRequest(BaseModel):
    task: str
    description: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatus(BaseModel):
    task_id: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

# Background task to run the agent
async def run_agent_task(task_id: str, task_description: str):
    try:
        # Update task status to running
        tasks_store[task_id]["status"] = "running"
        
        # Create and run agent
        agent = Agent(task=task_description, llm=llm)
        result = await agent.run()
        
        # Update task status to completed
        tasks_store[task_id].update({
            "status": "completed",
            "result": str(result) if result else "Task completed successfully",
            "completed_at": datetime.now()
        })
        
    except Exception as e:
        # Update task status to failed
        tasks_store[task_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now()
        })

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Browser Agent API",
        "version": "1.0.0",
        "endpoints": {
            "POST /tasks": "Create a new browser automation task",
            "GET /tasks/{task_id}": "Get task status and result",
            "GET /tasks": "List all tasks",
            "DELETE /tasks/{task_id}": "Delete a task"
        }
    }

@app.post("/tasks", response_model=TaskResponse)
async def create_task(task_request: TaskRequest, background_tasks: BackgroundTasks):
    """Create a new browser automation task"""
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    # Store task information
    tasks_store[task_id] = {
        "task_id": task_id,
        "task": task_request.task,
        "description": task_request.description,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": datetime.now(),
        "completed_at": None
    }
    
    # Add task to background tasks
    background_tasks.add_task(run_agent_task, task_id, task_request.task)
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message="Task created successfully and is being processed"
    )

@app.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get the status and result of a specific task"""
    
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = tasks_store[task_id]
    return TaskStatus(**task_data)

@app.get("/tasks")
async def list_tasks():
    """List all tasks"""
    return {
        "tasks": list(tasks_store.values()),
        "total": len(tasks_store)
    }

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a specific task"""
    
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    deleted_task = tasks_store.pop(task_id)
    return {
        "message": "Task deleted successfully",
        "task_id": task_id,
        "task": deleted_task["task"]
    }

@app.post("/tasks/flight-search")
async def search_flight(
    origin: str, 
    destination: str, 
    weeks_ahead: int = 3,
    background_tasks: BackgroundTasks
):
    """Specific endpoint for flight searches on Kayak"""
    
    task_description = f"Go to kayak.com and find the cheapest one-way flight from {origin} to {destination} in {weeks_ahead} weeks."
    
    task_request = TaskRequest(
        task=task_description,
        description=f"Flight search from {origin} to {destination}"
    )
    
    return await create_task(task_request, background_tasks)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
