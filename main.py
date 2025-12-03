# cli and convo management
import cli
import convo_manager

# conversation logic
def main():
    cli.print_welcome()
    convo_manager.start_conversation()
    #assign chatid, manage convo state, etc.    
    save_conversation_state()