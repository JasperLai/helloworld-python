def hello_world():
    """
    A simple function that prints 'Hello, World!' to the console.
    """
    print("Hello, World!")

def greet(name: str) -> str:
    """
    Greets a person by name.
    
    Args:
        name (str): The name of the person to greet
        
    Returns:
        str: A greeting message
    """
    return f"Hello, {name}!"

if __name__ == "__main__":
    hello_world()
    print(greet("GitHub"))