#!/usr/bin/env python3
"""
Interactive Chat Demo with Ollama
Shows the agent using layered context with actual LLM responses
"""

from agent import get_agent
import json
import os
import tkinter as tk
from tkinter import simpledialog, Listbox, END, SINGLE
from utils import append_to_conversation, log


def set_convo_id():
    """Generate a unique conversation ID"""

    from uuid import uuid4
    convo_id = str(uuid4())
    return convo_id

def name_convo():
    name = input("Enter a name for this conversation: ").strip()
    if not name:
        name = "Unnamed Conversation"
    #later: name with llm
    return name

def load_convo(convo_id: str, convo_name: str = ""):
    """Load and continue an existing conversation by id."""
    convo_path = f"Stimuli/{convo_id}.txt"
    if not os.path.exists(convo_path):
        print(f"Conversation file not found: {convo_path}")
        return

    # Read existing conversation
    with open(convo_path, "r") as f:
        history = f.read()

    print("=" * 60)
    print(f"Resuming Chat\nConversation ID: {convo_id}\nConversation Name: {convo_name}\nModel: gpt-oss:20b-cloud\n")
    if history.strip():
        print("Previous conversation:")
        print(history[-2000:])  # Show last 2000 chars
        print("..." if len(history) > 2000 else "")
        print()

    agent = get_agent()
    print(f"👋 Agent '{agent.name}' is ready!")
    print("   (Type 'quit' to exit, 'status' for agent info)")
    print()

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            append_to_conversation("User ended the chat session.", convo_id=convo_id)
            break

        if user_input.lower() == 'status':
            print("\n🧠 Agent Status:")
            print(json.dumps(agent.introspect(), indent=2))
            append_to_conversation(f"Agent status requested: {json.dumps(agent.introspect())}", convo_id=convo_id)
            print()
            continue

        # Generate response using agent's built-in method
        print(f"\n{agent.name}: ", end="", flush=True)
        response = agent.generate(user_input, convo=history[-2000:])
        print(response)
        print()

        # Append to conversation file
        append_to_conversation(f"User: {user_input}", convo_id=convo_id)
        append_to_conversation(f"{agent.name}: {response}", convo_id=convo_id)
    
def new_chat():
    convo_id = set_convo_id()
    convo_name = name_convo()
    #create file with id 
    with open(f"Stimuli/{convo_id}.txt", "w") as convo_file:
        convo_file.write("")

    log(f"New conversation started: {convo_id}")
    append_to_conversation(f"Conversation started, {convo_name}.", convo_id=convo_id)

    print("=" * 60)
    print(f"Interactive Chat with Layered Memory Agent\nConversation ID: {convo_id}\nConversation Name: {convo_name}\n Model: gpt-oss:20b-cloud\n")

    
    agent = get_agent()
    print(f"👋 Agent '{agent.name}' is ready!")
    print("   (Type 'quit' to exit, 'status' for agent info)")
    print()
    
    while True:
        user_input = input("You: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            append_to_conversation("User ended the chat session.", convo_id=convo_id)
            break
        
        if user_input.lower() == 'status':
            print("\n🧠 Agent Status:")
            print(json.dumps(agent.introspect(), indent=2))
            append_to_conversation(f"Agent status requested: {json.dumps(agent.introspect())}", convo_id=convo_id)
            print()
            continue
        
    
    
        
        # Generate response using agent's built-in method
        print(f"\n{agent.name}: ", end="", flush=True)
        response = agent.generate(user_input)
        print(response)
        print()

        # Append to conversation file
        append_to_conversation(f"User: {user_input}", convo_id=convo_id)
        append_to_conversation(f"{agent.name}: {response}", convo_id=convo_id)


def get_old_chats():
    """Load chats as list from Stimuli folder."""
    chats = []
    stimuli_path = "Stimuli"
    if not os.path.exists(stimuli_path):
        return chats

    for filename in os.listdir(stimuli_path):
        if filename.endswith(".txt") and filename != "conversation.txt" and filename != "readme.md":
            convo_id = filename.replace(".txt", "")
            # Try to extract name from first line of file
            filepath = os.path.join(stimuli_path, filename)
            name = convo_id[:8]  # default: first 8 chars of id
            try:
                with open(filepath, "r") as f:
                    first_line = f.readline().strip()
                    if first_line.startswith("Conversation started,"):
                        name = first_line.replace("Conversation started,", "").strip().rstrip(".")
            except Exception:
                pass
            chats.append({"id": convo_id, "name": name or convo_id[:8]})
    return chats

def show_chat_dialog(chats):
    """Show a tkinter dialog to select from old chats."""
    selected = [None]

    def on_select():
        sel = listbox.curselection()
        if sel:
            selected[0] = chats[sel[0]]
        root.destroy()

    def on_new():
        selected[0] = "NEW" # type: ignore
        root.destroy()

    root = tk.Tk()
    root.title("Select Chat")
    root.geometry("400x300")

    tk.Label(root, text="Select a conversation to continue:", font=("Arial", 12)).pack(pady=10)

    listbox = Listbox(root, selectmode=SINGLE, font=("Arial", 11), width=50, height=10)
    for chat in chats:
        listbox.insert(END, f"{chat['name']} — {chat['id'][:8]}...")
    listbox.pack(pady=10)

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)

    tk.Button(btn_frame, text="Continue Selected", command=on_select, width=15).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="New Chat", command=on_new, width=15).pack(side=tk.LEFT, padx=5)

    root.mainloop()
    return selected[0]

def choose_chat():
    print("Select Chat Mode:")
    print("1. New Chat")
    print("2. Choose old chat")
    choice = input("Enter choice (1,2): ").strip()

    if choice == '1':
        new_chat()
    elif choice == '2':
        chats = get_old_chats()
        if not chats:
            print("No previous chats found. Starting New Chat.")
            new_chat()
            return

        # Show GUI dialog
        selected = show_chat_dialog(chats)

        if selected == "NEW" or selected is None:
            new_chat()
        else:
            load_convo(selected['id'], selected['name'])
    else:
        print("Invalid choice. Starting New Chat by default.")
        new_chat()
if __name__ == "__main__":
    choose_chat()
