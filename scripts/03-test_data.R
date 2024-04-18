#### Preamble ####
# Purpose: Tests the cleaned music industry dataset
# Author: Liban Timir
# Date: 18 April 2024
# Contact: liban.timir@utoronto.ca
# License: MIT
# Pre-requisites: 02-data_cleaning.R


#### Workspace setup ####
library(tidyverse) #loads the tidyverse library
library(testthat) #loads the testthat library

#### Test data ####
music_data <- read_csv("/Users/victortimir/music-industry-analysis/data/analysis_data/musicdata.csv")

test_that("All expected columns are present", {
  expect_true(all(c("format", "year", "value_actual") %in% 
                    colnames(music_data)))
})
#tests if the cleaned data has the expected columns

test_that("No missing values in crucial columns", {
  expect_equal(sum(is.na(music_data$year)), 0)
  expect_equal(sum(is.na(music_data$value_actual)), 0)
})
#tests if there are no missing values

test_that("Year column contains valid years", {
  expect_true(all(music_data$year >= 1973 & music_data$year <= 2020))
})
#tests that the year column contains only valid years

test_that("Value column doesn't contain unreasonably high values", {
  expect_true(all(music_data$value_actual <= 10000000))
})
#tests that the value column doesn't contain values exceeding 10000000
