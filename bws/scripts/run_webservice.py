#!/usr/bin/env python3
#
# Run a risk prediction via the web-service.
#
# optional arguments:
#  -h, --help            show this help message and exit
#  --mut_freq {UK,Ashkenazi,Iceland,Custom}
#                        Mutation Frequencies (default: UK)
#  --cancer_rates {UK,Australia,Canada,USA-white,Denmark,Finland,Iceland,New-Zealand,Norway,Spain,Sweden}
#                        Cancer incidence rates (default: UK)
#  --url URL             Web-services URL
#  -u USER, --user USER  Username
#  -p PEDIGREE, --pedigree PEDIGREE
#                        Pedigree file
#
# Gene mutation frequencies (when --mut_freq Custom):
#  --brca1_mut_frequency BRCA1_MUT_FREQUENCY
#                        brca1 mutation frequency
#  --brca2_mut_frequency BRCA2_MUT_FREQUENCY
#                        brca2 mutation frequency
#  --palb2_mut_frequency PALB2_MUT_FREQUENCY
#                        palb2 mutation frequency
#  --chek2_mut_frequency CHEK2_MUT_FREQUENCY
#                        chek2 mutation frequency
#  --atm_mut_frequency ATM_MUT_FREQUENCY
#                        atm mutation frequency
#
# Genetic test sensitivity:
#  --brca1_mut_sensitivity BRCA1_MUT_SENSITIVITY
#                        brca1 mutation sensitivity
#  --brca2_mut_sensitivity BRCA2_MUT_SENSITIVITY
#                        brca2 mutation sensitivity
#  --palb2_mut_sensitivity PALB2_MUT_SENSITIVITY
#                        palb2 mutation sensitivity
#  --chek2_mut_sensitivity CHEK2_MUT_SENSITIVITY
#                        chek2 mutation sensitivity
#  --atm_mut_sensitivity ATM_MUT_SENSITIVITY
#                        atm mutation sensitivity
#
# e.g.
# run_webservice.py -u username -p ~/bwa4_beta_pedigree_data.txt
#
# run_webservice.py --mut_freq Custom --brca1_mut_frequency 0.00064 --brca2_mut_frequency 0.00102 \
#      --palb2_mut_frequency 0.000575 --chek2_mut_frequency 0.002614 --atm_mut_frequency 0.001921
#
# run_webservice.py -u username -p bws/bws/tests/data/canrisk_multi4x.txt -c both -t example.tab
#

import getpass
import requests
import json
import argparse
import csv

#
# define optional command line arguments
parser = argparse.ArgumentParser('run a risk prediction via the web-service')
parser.add_argument('-c', '--can', default='boadicea', choices=['boadicea', 'ovarian', 'both'],
                    help='Cancer risk models')
parser.add_argument('--mut_freq', default='UK', choices=['UK', 'Ashkenazi', 'Iceland', 'Custom'],
                    help='Mutation Frequencies (default: %(default)s)')

bc_genes = ['brca1', 'brca2', 'palb2', 'chek2', 'atm']
oc_genes = ['brca1', 'brca2', 'rad51c', 'rad51d', 'brip1']
genes = list(set(bc_genes + oc_genes))

group1 = parser.add_argument_group('Gene mutation frequencies (when --mut_freq Custom)')
for gene in genes:
    group1.add_argument('--'+gene+'_mut_frequency', type=float, help=gene+' mutation frequency')

group2 = parser.add_argument_group('Genetic test sensitivity')
for gene in genes:
    group2.add_argument('--'+gene+'_mut_sensitivity', type=float, help=gene+' mutation sensitivity')

parser.add_argument('--cancer_rates', default='UK',
                    choices=['UK', 'Australia', 'Canada', 'USA-white', 'Denmark', 'Finland',
                             'Iceland', 'New-Zealand', 'Norway', 'Spain', 'Sweden'],
                    help='Cancer incidence rates (default: %(default)s)')

parser.add_argument('--url', default='https://canrisk.org/', help='Web-services URL')
parser.add_argument('-u', '--user', help='Username')
parser.add_argument('-p', '--ped', help='CanRisk (or BOADICEA v4) pedigree file')
parser.add_argument('-t', '--tab', help='Tab delimeted output file name')

args = parser.parse_args()

if args.can == "both":
    cancers = ['boadicea', 'ovarian']
    genes = list(set(bc_genes + oc_genes))
elif args.can == "ovarian":
    cancers = ['ovarian']
    genes = oc_genes
else:
    cancers = ['boadicea']
    genes = bc_genes

data = {"user_id": "end_user_id"}
if args.mut_freq == 'Custom':
    for gene in genes:
        if args.__dict__[gene+"_mut_frequency"] is None:
            print("--mut_freq Custom requires --"+gene+"_mut_frequency")
            exit(1)
        else:
            data[gene+"_mut_frequency"] = args.__dict__[gene+"_mut_frequency"]

for gene in genes:
    if args.__dict__[gene+"_mut_sensitivity"] is not None:
        data[gene+"_mut_sensitivity"] = args.__dict__[gene+"_mut_sensitivity"]

#
# prompt for required inputs
if args.user is None:
    user = input("Username: ")
else:
    user = args.user
pwd = getpass.getpass()
url = args.url

# 1. request an authentication token
r = requests.post(url+"auth-token/", data={"username": user, "password": pwd})
if r.status_code == 200:
    token = r.json()['token']
else:
    print("Error status: "+str(r.status_code))
    exit(1)

# 2. run BOADICEA risk prediction for a given pedigree
bwa = input("Pedigree (BOADICEA v4 file): ") if args.ped is None else args.ped

data["mut_freq"] = args.mut_freq
data["cancer_rates"] = args.cancer_rates

# open output file
if args.tab:
    open(args.tab, 'w')

for cmodel in cancers:
    files = {'pedigree_data': open(bwa, 'rb')}
    r = requests.post(url+cmodel+'/', data=data, files=files, auth=(user, pwd))
    if r.status_code == 200:
        rjson = r.json()

        # tab delimeted output file
        if args.tab:
            if cmodel == "boadicea":
                header = ["FamID", "IndivID", "Age", "BCRisk          ", "BCRisk%    ", "OCRisk          ", "OCRisk%"]
            else:
                header = ["FamID", "IndivID", "Age", "OCRisk          ", "OCRisk%"]
            with open(args.tab, 'a') as csvfile:
                writer = csv.writer(csvfile, delimiter='\t')
                writer.writerow(["version", rjson["version"]])
                writer.writerow(["timestamp", rjson["timestamp"]])
                writer.writerow(["cancer incidence rates", rjson["cancer_incidence_rates"]])
                writer.writerow(["note: baseline cancer risks are provided in brackets"])
                results = rjson["pedigree_result"]
                for res in results:
                    famid = res["family_id"]
                    indivID = res["proband_id"]
                    cancer_risks = res["cancer_risks"]
                    bcancer_risks = res["baseline_cancer_risks"]

                    writer.writerow(header)
                    for idx, cr in enumerate(cancer_risks):
                        bcr = bcancer_risks[idx]
                        if bcr["age"] == cr["age"]:
                            if cmodel == "boadicea":
                                bc_dec = '{} ({})'.format(cr["breast cancer risk"]["decimal"],
                                                          bcr["breast cancer risk"]["decimal"])
                                bc_per = '{} ({})'.format(cr["breast cancer risk"]["percent"],
                                                          bcr["breast cancer risk"]["percent"])
                            oc_dec = '{} ({})'.format(cr["ovarian cancer risk"]["decimal"],
                                                      bcr["ovarian cancer risk"]["decimal"])
                            oc_per = '{} ({})'.format(cr["ovarian cancer risk"]["percent"],
                                                      bcr["ovarian cancer risk"]["percent"])
                            if cmodel == "boadicea":
                                writer.writerow([famid, indivID, cr["age"], bc_dec, bc_per, oc_dec, oc_per])
                            else:
                                writer.writerow([famid, indivID, cr["age"], oc_dec, oc_per])
                    writer.writerow([])
            csvfile.close()
        else:
            print(json.dumps(rjson, indent=4, sort_keys=True))
    else:
        print("Error status: "+str(r.status_code))
        print(r.json())
        exit(1)