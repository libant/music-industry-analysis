#### Preamble ####
# Purpose: Cleans the raw music data recorded by three observers from Kaggle
# Author: Liban Timir
# Date: 18 April 2024
# Contact: liban.timir@mail.utoronto.ca
# License: MIT
# Pre-requisites: 01-download_data.R

#### Workspace setup ####
library(tidyverse)

#### Clean data ####
music_data <- read_csv("data/raw_data/MusicData.csv")

music_data <- music_data %>%
  clean_names() %>%
  select(-index) %>% 
  select(-number_of_records) %>%
  mutate(
    year = as.numeric(year),
    value_actual = ifelse(is.na(value_actual), 0, value_actual)
  ) %>%
  drop_na()

#### Save data ####
write_csv(cleaned_data, "data/analysis_data/analysis_data.csv")
