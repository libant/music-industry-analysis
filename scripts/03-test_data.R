#### Preamble ####
# Purpose: Tests the cleaned music industry dataset
# Author: Liban Timir
# Date: 18 April 2024
# Contact: liban.timir@utoronto.ca
# License: MIT
# Pre-requisites: 02-data_cleaning.R


#### Workspace setup ####
library(tidyverse)
library(testthat)

#### Test data ####
cleaned_data <- read_csv("data/analysis_data/analysis_data.csv")

test_that("All expected columns are present", {
  expect_true(all(c("Format", "Metric", "Year", "Value (Actual)") %in% 
                    colnames(music_data)))
})

test_that("No missing values in crucial columns", {
  expect_equal(sum(is.na(music_data$year)), 0)
  expect_equal(sum(is.na(music_data$value_actual)), 0)
})

test_that("Year column contains valid years", {
  expect_true(all(music_data$year >= 1973 & music_data$year <= 2020))
})

test_that("Value (Actual) column contains non-negative numbers", {
  expect_true(all(music_data$value_actual >= 0))
})
