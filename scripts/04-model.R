#### Preamble ####
# Purpose: Models the music industry dataset
# Author: Liban Timir
# Date: 18 April 2024
# Contact: liban.timir@mail.utoronto.ca
# License: MIT
# Pre-requisites: 02-data_cleaning.R


#### Workspace setup ####
library(tidyverse)
library(rstanarm)

#### Read data ####
cleaned_data <- read_csv("data/analysis_data/analysis_data.csv")

### Model data ####
music_data <- music_data %>%
  mutate(format_binary = if_else(format == "Digital", 1, 0)) 

music_model <- 
  stan_glm(
    formula = value_actual ~ year + format_binary,
    data = music_data,
    family = gaussian(),
    prior = normal(location = 0, scale = 2.5, autoscale = TRUE),
    prior_intercept = normal(location = 0, scale = 2.5, autoscale = TRUE),
    prior_aux = exponential(rate = 1, autoscale = TRUE),
    seed = 555
  )


#### Save model ####
saveRDS(
  music_model,
  file = "models/first_model.rds"
)


