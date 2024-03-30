#### Preamble ####
# Purpose: Simulates the RIAA dataset
# Author: Liban Timir
# Date: 18 April 2024 
# Contact: liban.timir@mail.utoronto.ca
# License: MIT



#### Workspace setup ####
library(tidyverse)

#### Simulate data ####
years <- 1973:2020

physical_sales_revenue <- c(seq(2000, 5000, length.out = 20), 
                            exp(seq(log(5000), log(500), length.out = 21)))

digital_sales_revenue <- c(rep(0, 20), 
                           exp(seq(log(1), log(7000), length.out = 21)))

total_units_sold <- c(seq(250, 400, length.out = 20), 
                      exp(seq(log(400), log(1000), length.out = 21)))

average_price_per_unit <- c(seq(8, 15, length.out = 20), 
                            exp(seq(log(15), log(2), length.out = 21)))

physical_distribution <- seq(1, 0, length.out = 48)
digital_distribution <- seq(0, 1, length.out = 48)

music_data <- tibble(Year = years,
                     Format = rep(c("Physical", "Digital"), 
                                  times = length(years)),
                     Revenue = c(physical_sales_revenue * physical_distribution, 
                                 digital_sales_revenue * digital_distribution))

print(head(music_data))


ggplot(music_data, aes(x = Year, y = Revenue, fill = Format)) +
  geom_bar(stat = "identity") +
  scale_fill_manual(values = c("Physical" = "red", "Digital" = "blue")) +
  labs(x = "Year", y = "Revenue ($M)", fill = "Format Type",
       title = "Music Sales Volumes by Format Type") +
  theme_minimal()




