# dyamically creates intervals for inference and updates global state
def make_thought_interval():
    # for now generate a random interval between 5 and 15 minutes,
    # this controls how often each module asks itself to reflect/update its state
    #extensions to consider:
    # - based on number of open tasks
    # - based on time of day
    # - based on user activity
    # - return interval in seconds
    import random
    interval = random.randint(5 * 60, 15 * 60)
    return interval 
def load_state():
    # placeholder for loading global state
    pass
    # could
    

def check_state():
    # placeholder for checking global state
    pass
    # could check for user activity, open tasks, etc.
    # state validation logic goes here

