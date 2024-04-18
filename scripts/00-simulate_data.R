#### Preamble ####
# Purpose: Simulates the RIAA dataset
# Author: Liban Timir
# Date: 18 April 2024 
# Contact: liban.timir@mail.utoronto.ca
# License: MIT


#### Workspace setup ####
library(tidyverse) #loads the tidyverse library
library(ggplot2) #loads the ggplot2 library

#### Simulate data ####
years <- 1973:2020 #creates the "year" variable

physical_sales_revenue <- c(seq(2000, 5000, length.out = 24), 
                            exp(seq(log(5000), log(500), length.out = 24)))
#simulates physical sales revenue

digital_sales_revenue <- c(rep(0, 24), 
                           exp(seq(log(1), log(7000), length.out = 24)))
#simulates digital sales revenue

physical_distribution <- seq(1, 0, length.out = 48)
digital_distribution <- seq(0, 1, length.out = 48)
#simulates linear distributions for physical and digital formats

interleaved_revenue <- numeric(length = 48)
interleaved_revenue[seq(1, 48, by = 2)] <- physical_sales_revenue * 
  physical_distribution[seq(1, 48, by = 2)]
interleaved_revenue[seq(2, 48, by = 2)] <- digital_sales_revenue * 
  digital_distribution[seq(2, 48, by = 2)]
#simulates revenue

music_data <- tibble(
  Year = years,
  Format = rep(c("Physical", "Digital"), each = 24),
  Revenue = interleaved_revenue
)

print(head(music_data))
#makes a tibble of the years, formats, and revenue simulated and displays them

ggplot(music_data, aes(x = Year, y = Revenue, fill = Format)) +
  geom_bar(stat = "identity") +
  scale_fill_manual(values = c("Physical" = "red", "Digital" = "blue")) +
  labs(x = "Year", y = "Revenue ($M)", fill = "Format Type",
       title = "Music Sales Volumes by Format Type") +
  theme_minimal()
#creates a bar graph using the simulated data


