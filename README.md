# An analysis of music industry data

## Overview

In this project, we examine data about the music industry, focusing on revenue trends across various music formats from 1973 to 2019. We estimate an Bayesian hierarchical model to further understand the effects of various music formats on industry revenue, taking into account temporal trends and potential interactions between formats. To replicate the steps in the analysis, you should go through each file in the "scripts" folder in numeric order, then you can compile the "paper" in the paper folder by rendering the .qmd file in R Markdown.

## File Structure

The repo is structured as:

-   `data/raw_data` contains the raw data as obtained from Kaggle user "Larxel" and that same data that was downloaded via RStudio.
-   `data/analysis_data` contains the cleaned dataset that was constructed.
-   `model` contains fitted models. 
-   `other` contains details about LLM chat interactions and sketches.
-   `paper` contains the files used to generate the paper, including the Quarto document and reference bibliography file, as well as the PDF of the paper. 
-   `scripts` contains the R scripts used to simulate, download and clean data in addition to some tests.


## Statement on LLM usage

Some aspects of the code were written with the help of ChatGPT and the entire chat history is available in other/llms/usage.txt.
