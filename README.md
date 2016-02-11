# DataPages
Static pages with convenient links to WTSI's pathogen sequencing data

## Scripts

This repo creates the following scripts which can be used to build static content directing users to WTSI's pathogen
datasets. 

* `datapages_update_projects`
* `datapages_update_nctc` (still under development)

This code needs priviledged access to some of our databases so it cannot be run outside Sanger.  In addition
some of the styling and javascript is inherited from the [Sanger website](https://www.sanger.ac.uk) so it isn't
a great idea to try running it locally. Instead, ask the web team to setup a sandbox for you and check your changes
there.

### `datapages_update_projects`

This script uses / abuses the word 'domain' to mean a collection of species as detailed in a configuration file
(e.g. [helminths.yml](pages_config/helminths.yml).

For each domain configuration file, it creates a new directory using the name taken from the config.  In this directory
it creates a `data` folder and an `index.html` page which is based on the [index.html](templates/index.html) template.

In effect, each domain gets it's own single page microsite.  On this page, users can select a species and can further
filter by project name.  When a different species is selected, javascript in the page fetches data in JSON format from
the relevant `/data` folder and renders it using [DataTables](http://datatables.net/).  It also updates other content
(fetched in the same query) including things like a species description and links to other resources.

Data for these pages is merged from a number of private and public sources:
* VRTrack database (mostly species name => project mapping and public accession ids)
* Sequencescape (public names for things like strain and sample name)
* ENA (to check if the run, project, sample is actually still available for download; if not it isn't displayed)
* Local config (metadata like database names, descriptive text, etc. see [pages_config](pages_config) for examples)
* Environment variables / `--global-config` (more sensitive details like database server names and user credentials)

## Installation

```
pip install git+https://github.com/sanger-pathogens/DataPages.git
```

You store your own config anywhere but it makes more sense to also clone this repo and use it to version config in the
[pages_config](pages_config) folder.
