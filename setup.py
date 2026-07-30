from setuptools import setup, find_packages

setup(
    name="terminal-agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "groq",
        "tavily-python",
        "python-dotenv",
        "click",
    ],
    entry_points={
        "console_scripts": [
            "tagent=agent.cli:cli",
        ],
    },
)