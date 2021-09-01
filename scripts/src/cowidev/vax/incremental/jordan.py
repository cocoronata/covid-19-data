import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from cowidev.utils.clean import clean_count
from cowidev.utils.web.scraping import get_soup, get_driver
from cowidev.vax.utils.incremental import enrich_data, increment
from cowidev.vax.utils.dates import localdate


class Jordan:
    def __init__(self):
        self.location = "Jordan"
        self.source_url = "https://corona.moh.gov.jo/ar"

    def read(self) -> pd.Series:
        return self._parse_data()

    def _parse_data(self) -> pd.Series:

        with get_driver(headless=True) as driver:
            # Main page
            driver.get(self._get_iframe_url())

            data_blocks = WebDriverWait(driver, 30).until(
                EC.visibility_of_all_elements_located((By.CLASS_NAME, "card"))
            )
            for block in data_blocks:
                block_title = block.get_attribute("aria-label")
                if "first dose" in block_title:
                    people_vaccinated = re.search(r"first dose +(\d+)\.", block_title).group(1)
                elif "sec dose" in block_title:
                    people_fully_vaccinated = re.search(r"sec dose +(\d+)\.", block_title).group(1)

            people_vaccinated = clean_count(people_vaccinated)
            people_fully_vaccinated = clean_count(people_fully_vaccinated)

        return pd.Series(
            {
                "people_vaccinated": people_vaccinated,
                "people_fully_vaccinated": people_fully_vaccinated,
            }
        )

    def _get_iframe_url(self):
        soup = get_soup(self.source_url, verify=False)
        url = soup.find("body").find_all("section")[1].find("iframe").get("src")
        return url

    def pipe_vaccinations(self, ds: pd.Series) -> pd.Series:
        total_vaccinations = ds.people_vaccinated + ds.people_fully_vaccinated
        return enrich_data(ds, "total_vaccinations", total_vaccinations)

    def pipe_date(self, ds: pd.Series) -> pd.Series:
        date = localdate("Asia/Amman")
        return enrich_data(ds, "date", date)

    def pipe_location(self, ds: pd.Series) -> pd.Series:
        return enrich_data(ds, "location", self.location)

    def pipe_vaccine(self, ds: pd.Series) -> pd.Series:
        # Johnson&Johnson authorized, no doses arrived or given yet
        vaccines_used = "Pfizer/BioNTech, Sinopharm/Beijing, Sputnik V, Oxford/AstraZeneca"
        return enrich_data(ds, "vaccine", vaccines_used)

    def pipe_source(self, ds: pd.Series) -> pd.Series:
        return enrich_data(ds, "source_url", self.source_url)

    def pipeline(self, ds: pd.Series) -> pd.Series:
        return (
            ds.pipe(self.pipe_vaccinations)
            .pipe(self.pipe_date)
            .pipe(self.pipe_location)
            .pipe(self.pipe_vaccine)
            .pipe(self.pipe_source)
        )

    def to_csv(self, paths):
        data = self.read().pipe(self.pipeline)
        increment(
            paths=paths,
            location=data["location"],
            total_vaccinations=data["total_vaccinations"],
            people_vaccinated=data["people_vaccinated"],
            people_fully_vaccinated=data["people_fully_vaccinated"],
            date=data["date"],
            source_url=data["source_url"],
            vaccine=data["vaccine"],
        )


def main(paths):
    # At the date of this automation, only the Arabic version of the website had the vaccination numbers
    Jordan().to_csv(paths)


if __name__ == "__main__":
    main()
