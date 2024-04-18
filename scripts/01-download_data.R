#### Preamble ####
# Purpose: Downloads and saves the data from Kabble
# Author: Liban Timir
# Date: 18 April 2024
# Contact: liban.timir@mail.utoronto.ca
# License: MIT



#### Workspace setup ####
library(tidyverse)
library(sf)

#### Download data ####
music_data <- read_csv("/Users/victortimir/music-industry-analysis/data/raw_data/musicdata-1.csv")

#### Save data ####
write_csv(music_data, "data/raw_data/rawmusicdata.csv") 

         
