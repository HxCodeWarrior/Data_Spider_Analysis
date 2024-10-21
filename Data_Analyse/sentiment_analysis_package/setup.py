from setuptools import setup, find_packages

setup(
    name='sentiment_analysis',
    version='1.0',
    packages=find_packages(),
    install_requires=[
        'torch',
        'transformers',
        'pandas',
        'numpy',
        'seaborn',
        'matplotlib',
        'scikit-learn'
    ],
    description='A package for sentiment analysis using BERT',
    author='Your Name',
    author_email='your.email@example.com'
)
