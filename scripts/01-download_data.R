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
music_data <- read_csv("/Users/victortimir/Downloads/MusicData.csv")

#### Save data ####
# change music_data to whatever name you assigned when you downloaded it.
write_csv(music_data, "data/raw_data/raw_data.csv") 

         
