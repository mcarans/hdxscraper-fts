#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
FTS:
---

Generates FTS datasets.

'''
import logging
from collections import OrderedDict
from os.path import join

from hdx.data.hdxobject import HDXError
from hdx.data.resource_view import ResourceView
from hdx.data.showcase import Showcase
from hdx.data.dataset import Dataset
from hdx.data.resource import Resource
from hdx.location.country import Country
from hdx.utilities.dictandlist import dict_of_lists_add, dict_of_sets_add
from hdx.utilities.downloader import DownloadError
from hdx.utilities.text import multiple_replace
from pandas import DataFrame, concat, to_numeric, Series, Index
from pandas.io.json import json_normalize
from slugify import slugify

logger = logging.getLogger(__name__)

funding_hxl_names = {
    'amountUSD': '#value+funding+total+usd',
    'boundary': '#financial+direction',
    'budgetYear': '#date+year+budget',
    'contributionType': '#financial+contribution+type',
    'createdAt': '#date+created',
    'date': '#date',
    'decisionDate': '#date+decision',
    'description': '#description+notes',
    'exchangeRate': '#financial+fx',
    'firstReportedDate': '#date+reported',
    'flowType': '#financial+contribution+type',
    'id': '#activity+id+fts_internal',
    'keywords': '#description+keywords',
    'method': '#financial+method',
    'originalAmount': '#value+funding+total',
    'originalCurrency': '#value+funding+total+currency',
    'refCode': '#activity+code',
    'status': '#status+text',
    'updatedAt': '#date+updated',
    'srcOrganization': '#org+name+funder',
    'srcOrganizationTypes': '#org+type+funder+list',
    'srcLocations': '#country+iso3+funder+list',
    'srcUsageYearStart': '#date+year+start+funder',
    'srcUsageYearEnd': '#date+year+end+funder',
    'destPlan': '#activity+appeal+name+impl',
    'destPlanCode': '#activity+appeal+id+external+impl',
    'destPlanId': '#activity+appeal+id+fts_internal+impl',
    'destOrganization': '#org+name+impl',
    'destOrganizationTypes': '#org+type+impl+list',
    'destGlobalClusters': '#sector+cluster+name+impl+list',
    'destLocations': '#country+iso3+impl+list',
    'destProject': '#activity+project+name+impl',
    'destProjectCode': '#activity+project+code+impl',
    'destUsageYearStart': '#date+year+start+impl',
    'destUsageYearEnd': '#date+year+end+impl'
}

hxl_names = {
    'id': '#activity+appeal+id+fts_internal',
    'countryCode': '#country+code',
    'name': '#activity+appeal+name',
    'code': '#activity+appeal+id+external',
    'revisedRequirements': '#value+funding+required+usd',
    'totalFunding': '#value+funding+total+usd',
    'startDate': '#date+start',
    'endDate': '#date+end',
    'year': '#date+year',
    'percentFunded': '#value+funding+pct',
    'clusterCode': '#sector+cluster+code',
    'clusterName': '#sector+cluster+name'
}

rename_columns = {
    'totalFunding': 'Funding',
    'revisedRequirements': 'Requirements',
    'percentFunded': 'Percent Funded',
    'clusterName': 'Cluster'
}

country_all_columns_to_keep = ['date', 'budgetYear', 'description', 'amountUSD', 'srcOrganization',
                               'srcOrganizationTypes', 'srcLocations', 'srcUsageYearStart', 'srcUsageYearEnd',
                               'destPlan', 'destPlanCode', 'destPlanId', 'destOrganization', 'destOrganizationTypes', 'destGlobalClusters', 'destLocations',
                               'destProject', 'destProjectCode', 'destUsageYearStart', 'destUsageYearEnd',
                               'contributionType', 'flowType', 'method', 'boundary', 'status', 'firstReportedDate',
                               'decisionDate', 'keywords', 'originalAmount', 'originalCurrency', 'exchangeRate', 'id',
                               'refCode', 'createdAt', 'updatedAt']
country_columns_to_keep = ['countryCode', 'id', 'name', 'code', 'startDate', 'endDate', 'year', 'revisedRequirements',
                           'totalFunding', 'percentFunded']
plan_columns_to_keep = ['clusterCode', 'clusterName', 'revisedRequirements', 'totalFunding']
cluster_columns_to_keep = ['countryCode', 'id', 'name', 'code', 'startDate', 'endDate', 'year', 'clusterCode',
                           'clusterName', 'revisedRequirements', 'totalFunding']


class FTSException(Exception):
    pass


def remove_fractions(df, colname):
    df[colname] = df[colname].astype(str)
    df[colname] = df[colname].str.split('.').str[0]


def drop_columns_except(df, columns_to_keep):
    # Drop unwanted columns.
    df = df.loc[:,columns_to_keep]
    return df


def drop_rows_with_col_word(df, columnname, word):
    # Drop unwanted rows
    pattern = r'\b%s\b' % word
    df = df[~df[columnname].str.contains(pattern, case=False)]
    return df


def hxlate(df, hxl_names):
    hxl_columns = [hxl_names[c] for c in df.columns]
    hxl = DataFrame.from_records([hxl_columns], columns=df.columns)
    df = concat([hxl, df])
    df.reset_index(inplace=True, drop=True)
    return df


def remove_nonenan(df, colname):
    df[colname] = df[colname].astype(str)
    df[colname].replace(['nan', 'none'], ['', ''], inplace=True)


def get_countries(base_url, downloader):
    url = '%slocation' % base_url
    response = downloader.download(url)
    json = response.json()
    return json['data']


def generate_dataset_and_showcase(base_url, downloader, folder, countryiso, countryname, locationid, today):
    '''
    api.hpc.tools/v1/public/fts/flow?countryISO3=CMR&Year=2016&groupby=cluster
    '''
    latestyear = str(today.year)
    title = '%s - Requirements and Funding Data' % countryname
    slugified_name = slugify('FTS Requirements and Funding Data for %s' % countryname).lower()

    dataset = Dataset({
        'name': slugified_name,
        'title': title,
    })
    dataset.set_maintainer('196196be-6037-4488-8b71-d786adf4c081')
    dataset.set_organization('fb7c2910-6080-4b66-8b4f-0be9b6dc4d8e')
    dataset.set_dataset_date_from_datetime(today)
    dataset.set_expected_update_frequency('Every day')
    dataset.set_subnational(False)
    try:
        dataset.add_country_location(countryiso)
    except HDXError as e:
        logger.error('%s has a problem! %s' % (title, e))
        return None, None, None

    tags = ['HXL', 'cash assistance', 'financial tracking service - fts', 'funding']
    dataset.add_tags(tags)

    showcase = Showcase({
        'name': '%s-showcase' % slugified_name,
        'title': 'FTS %s Summary Page' % countryname,
        'notes': 'Click the image on the right to go to the FTS funding summary page for %s' % countryname,
        'url': 'https://fts.unocha.org/countries/%s/flows/2017' % locationid,
        'image_url': 'https://fts.unocha.org/sites/default/files/styles/fts_feature_image/public/navigation_101.jpg'
    })
    showcase.add_tags(tags)

    file_to_upload_funddet = None
    funding_url = '%sfts/flow?countryISO3=%s&year=%s' % (base_url, countryiso, latestyear)
    r = downloader.download(funding_url)
    fund_data = r.json()['data']['flows']
    dffunddet = json_normalize(fund_data)

    def add_objects(name):
        def flatten_objects(x):
            outputdicts = OrderedDict()
            typedicts = OrderedDict()
            for infodict in x:
                infodicttype = infodict['type']
                typedict = typedicts.get(infodicttype, OrderedDict())
                for key in infodict:
                    if key not in ['type', 'behavior', 'id'] or (infodicttype == 'Plan' and key == 'id'):
                        value = infodict[key]
                        if isinstance(value, list):
                            for element in value:
                                dict_of_lists_add(typedict, key, element)
                        else:
                            dict_of_lists_add(typedict, key, value)
                typedicts[infodicttype] = typedict
            for objectType in typedicts:
                prefix = '%s%s' % (name, objectType)
                for key in typedicts[objectType]:
                    keyname = '%s%s' % (prefix, key.capitalize())
                    values = typedicts[objectType][key]
                    replacements = {'OrganizationOrganization': 'Organization', 'Name': '', 'types': 'Types',
                                    'code': 'Code', 'source': 'src', 'destination': 'dest'}
                    keyname = multiple_replace(keyname, replacements)
                    if 'UsageYear' in keyname:
                        values = sorted(values)
                        outputdicts['%sStart' % keyname] = values[0]
                        outputstr = values[-1]
                        keyname = '%sEnd' % keyname
                    elif any(x in keyname for x in ['Cluster', 'Location', 'OrganizationTypes']):
                        if keyname[-1] != 's':
                            keyname = '%ss' % keyname
                        if 'Location' in keyname:
                            iso3s = list()
                            for country in values:
                                iso3s.append(Country.get_iso3_country_code_fuzzy(country)[0])
                            values = iso3s
                        outputstr = ','.join(sorted(values))
                    else:
                        if len(values) > 1:
                            outputstr = 'Multiple'
                            logger.error('Multiple used instead of %s for %s in %s' % (values, keyname, countryname))
                        else:
                            outputstr = values[0]
                    outputdicts[keyname] = outputstr
            return outputdicts

        typedicts = dffunddet['%sObjects' % name].apply(flatten_objects)
        return dffunddet.join(DataFrame(list(typedicts)))

    if 'sourceObjects' in dffunddet:
        dffunddet = add_objects('source')
        dffunddet = add_objects('destination')

        def get_keywords(x):
            if x:
                return ','.join(x)
            else:
                return ''

        dffunddet['keywords'] = dffunddet.keywords.apply(get_keywords)
        if 'originalAmount' not in dffunddet:
            dffunddet['originalAmount'] = ''
        if 'originalCurrency' not in dffunddet:
            dffunddet['originalCurrency'] = ''
        if 'refCode' not in dffunddet:
            dffunddet['refCode'] = ''
        dffunddet = drop_columns_except(dffunddet, country_all_columns_to_keep)
        dffunddet.sort_values('date', ascending=False, inplace=True)
        dffunddet.date = dffunddet.date.str[:10]
        dffunddet.firstReportedDate = dffunddet.firstReportedDate.str[:10]
        dffunddet.decisionDate = dffunddet.decisionDate.str[:10]
        dffunddet.createdAt = dffunddet.createdAt.str[:10]
        dffunddet.updatedAt = dffunddet.updatedAt.str[:10]
        # add HXL tags
        dffunddet = hxlate(dffunddet, funding_hxl_names)
        dffunddet.rename(index=str, columns=rename_columns, inplace=True)

        filename = 'fts_funding_%s.csv' % countryiso.lower()
        file_to_upload_funddet = join(folder, filename)

        resource_data = {
            'name': filename.lower(),
            'description': 'FTS Detailed Funding Data for %s for %s' % (countryname, latestyear),
            'format': 'csv'
        }
        resource = Resource(resource_data)
        resource.set_file_to_upload(file_to_upload_funddet)
        dataset.add_update_resource(resource)

    planidcodemapping = dict()
    requirements_url = '%splan/country/%s' % (base_url, countryiso)
    funding_url = '%sfts/flow?groupby=plan&countryISO3=%s' % (base_url, countryiso)
    r = downloader.download(requirements_url)
    req_data = r.json()['data']
    r = downloader.download(funding_url)
    data = r.json()['data']['report3']['fundingTotals']['objects']
    if len(data) == 0:
        fund_data = None
    else:
        fund_data = data[0].get('objectsBreakdown')
    if len(req_data) == 0:
        if not fund_data:
            if file_to_upload_funddet:
                logger.error('We have latest year funding data but no overall funding data for %s' % title)
                dffunddet.to_csv(file_to_upload_funddet, encoding='utf-8', index=False, date_format='%Y-%m-%d')
                return dataset, showcase, None
            logger.warning('No requirements or funding data available')
            return None, None, None
        logger.warning('No requirements data, only funding data available')
        dfreq = None
        dffund = json_normalize(fund_data)
        dffund.totalFunding += dffund.onBoundaryFunding
        dffund = drop_columns_except(dffund, country_columns_to_keep)
        dffund['percentFunded'] = ''
        dffund.fillna('', inplace=True)
        dffundreq = dffund
    else:
        dfreq = json_normalize(req_data)
        dfreq['year'] = dfreq['years'].apply(lambda x: x[0]['year'])
        if bool(dfreq['years'].apply(lambda x: len(x) != 1).any()) is True:
            logger.error('More than one year listed in a plan for %s!' % countryname)
        dfreq['id'] = dfreq.id.astype(str).str.replace('\\.0', '')
        planidcodemapping.update(Series(dfreq.code.values, index=dfreq.id).to_dict())
        if fund_data:
            dffund = json_normalize(fund_data)
            if 'id' in dffund:
                dffundreq = dfreq.merge(dffund, on='id', how='outer', validate='1:1')
                dffundreq.name_x.fillna(dffundreq.name_y, inplace=True)
                dffundreq.fillna('', inplace=True)
                dffundreq.totalFunding += dffundreq.onBoundaryFunding
                dffundreq['percentFunded'] = (to_numeric(dffundreq.totalFunding) / to_numeric(
                    dffundreq.revisedRequirements) * 100).astype(str)
            else:
                logger.info('Funding data lacks plan ids')
                dffundreq = dfreq
                dffundreq['totalFunding'] = ''
                dffundreq['percentFunded'] = '0'
                dffund.totalFunding += dffund.onBoundaryFunding
                dffund = drop_columns_except(dffund, country_columns_to_keep)
                dffund['percentFunded'] = ''
                dffund.fillna('', inplace=True)
                dffundreq = dffundreq.append(dffund)
        else:
            logger.warning('No funding data, only requirements data available')
            dffundreq = dfreq
            dffundreq['totalFunding'] = ''
            dffundreq['percentFunded'] = '0'
    dffundreq['countryCode'] = countryiso
    dffundreq.rename(columns={'name_x': 'name'}, inplace=True)
    dffundreq = drop_columns_except(dffundreq, country_columns_to_keep)
    dffundreq.sort_values('endDate', ascending=False, inplace=True)
    dffundreq.startDate = dffundreq.startDate.str[:10]
    dffundreq.endDate = dffundreq.endDate.str[:10]
    # convert floats to string and trim ( formatters don't work on columns with mixed types)
    remove_fractions(dffundreq, 'revisedRequirements')
    remove_nonenan(dffundreq, 'revisedRequirements')
    remove_fractions(dffundreq, 'totalFunding')
    remove_nonenan(dffundreq, 'totalFunding')
    dffundreq['id'] = dffundreq['id'].astype(str)
    remove_fractions(dffundreq, 'id')
    remove_nonenan(dffundreq, 'id')
    remove_fractions(dffundreq, 'percentFunded')
    remove_nonenan(dffundreq, 'percentFunded')
    # sort
    dffundreq.sort_values(['endDate'], ascending=[False], inplace=True)
    dffundreq = drop_rows_with_col_word(dffundreq, 'name', 'test')
    # add HXL tags
    hxldffundreq = hxlate(dffundreq, hxl_names)
    hxldffundreq.rename(index=str, columns=rename_columns, inplace=True)

    filename = 'fts_requirements_funding_%s.csv' % countryiso.lower()
    file_to_upload_hxldffundreq = join(folder, filename)

    resource_data = {
        'name': filename.lower(),
        'description': 'FTS Annual Requirements and Funding Data for %s' % countryname,
        'format': 'csv'
    }
    resource = Resource(resource_data)
    resource.set_file_to_upload(file_to_upload_hxldffundreq)
    dataset.add_update_resource(resource)

    def fill_row(planid, row):
        plan_url = '%splan/id/%s' % (base_url, planid)
        r = downloader.download(plan_url)
        data = r.json()['data']
        error = data.get('message')
        if error:
            raise FTSException(error)
        code = data['code']
        planidcodemapping[planid] = code
        row['code'] = code
        row['startDate'] = str(data['startDate'])[:10]
        row['endDate'] = str(data['endDate'])[:10]
        years = data['years']
        if len(years) > 1:
            logger.error('More than one year listed in plan %s for %s!' % (planid, countryname))
        row['year'] = years[0]['year']
        locations = data['locations']
        if len(locations) == 0:
            return True
        for location in data['locations']:
            adminlevel = location.get('adminlevel', location.get('adminLevel'))
            if adminlevel == 0 and location['iso3'] != countryiso:
                return True
        return False

    if dfreq is None:
        reqplanids = None
    else:
        reqplanids = drop_columns_except(dfreq, ['id', 'locations'])
    combined = DataFrame()
    multilocwarning = 'Plan %s spans multiple locations - ignoring in cluster breakdown (%s)!'
    for i, row in hxldffundreq.iterrows():
        if i == '0':
            continue
        planid = row['id']
        if planid == '' or planid == 'undefined':
            planname = row['name']
            if planname == 'Not specified':
                continue
            raise FTSException('Plan Name: %s is invalid!' % planname)
        else:
            loc_funding_url = '%sfts/flow?planid=%s&groupby=location' % (base_url, planid)
            try:
                r = downloader.download(loc_funding_url)
                loc_data = r.json()['data']
                loc_fund_objects = loc_data['report3']['fundingTotals']['objects']
                totalfunding = row['Funding']
                try:
                    origfunding = int(totalfunding)
                except ValueError:
                    origfunding = None
                totalrequirements = row['Requirements']
                try:
                    origrequirements = int(totalrequirements)
                except ValueError:
                    origrequirements = None
                if len(loc_fund_objects) != 0:
                    for location in loc_fund_objects[0]['objectsBreakdown']:
                        if Country.get_iso3_country_code_fuzzy(location['name'])[0] != countryiso:
                            continue
                        totalfunding = location['totalFunding']
                        if isinstance(totalfunding, int):
                            boundaryfunding = location['onBoundaryFunding']
                            if isinstance(boundaryfunding, int):
                                totalfunding += boundaryfunding
                            if origfunding != totalfunding:
                                #logger.warning('Overriding funding')
                                row['Funding'] = totalfunding
                        break
                loc_req_objects = loc_data['requirements']['objects']
                if loc_req_objects:
                    for location in loc_req_objects:
                        if Country.get_iso3_country_code_fuzzy(location['name'])[0] != countryiso:
                            continue
                        totalrequirements = location['revisedRequirements']
                        if isinstance(totalrequirements, int):
                            if origrequirements != totalrequirements:
                                #logger.warning('Overriding requirements for %s' % planid)
                                row['Requirements'] = totalrequirements
                        break
                if totalrequirements:
                    if totalfunding == '':
                        row['Percent Funded'] = '0'
                    else:
                        row['Percent Funded'] = str(int(int(totalfunding) / int(totalrequirements) * 100))
                else:
                    row['Percent Funded'] = ''
            except DownloadError:
                logger.error('Problem with downloading %s!' % loc_funding_url)

            try:
                if reqplanids is not None:
                    planlocations = reqplanids.loc[reqplanids['id'] == planid].squeeze()
                    if len(planlocations) == 0:
                        if fill_row(planid, row):
                            logger.warning(multilocwarning % (planid, 'no locations in req plan info'))
                            continue
                    else:
                        if len(planlocations['locations']) > 1:
                            logger.warning(multilocwarning % (planid, '>1 locations in req plan info'))
                            continue
                else:
                    if fill_row(planid, row):
                        logger.warning(multilocwarning % (planid, 'no req plan info'))
                        continue
            except FTSException as ex:
                logger.error(ex)
                continue

        funding_url = '%sfts/flow?planid=%s&groupby=cluster' % (base_url, planid)
        try:
            r = downloader.download(funding_url)
            data = r.json()['data']
            fund_objects = data['report3']['fundingTotals']['objects']
            if len(fund_objects) == 0:
                logger.warning('%s has no funding objects!' % funding_url)
                fund_data_cluster = None
            else:
                fund_data_cluster = fund_objects[0]['objectsBreakdown']
        except DownloadError:
            logger.error('Problem with downloading %s!' % funding_url)
            continue
        req_data_cluster = data['requirements']['objects']
        if req_data_cluster:
            dfreq_cluster = json_normalize(req_data_cluster)
            if 'id' not in dfreq_cluster:
                dfreq_cluster['id'] = ''
            else:
                dfreq_cluster['id'] = dfreq_cluster.id.astype(str).str.replace('\\.0', '')
            if fund_data_cluster:
                dffund_cluster = json_normalize(fund_data_cluster)
                if 'id' not in dffund_cluster:
                    dffund_cluster['id'] = ''
                df = dffund_cluster.merge(dfreq_cluster, on='id', how='outer', validate='1:1')
                df.rename(columns={'name_x': 'clusterName'}, inplace=True)
                df.clusterName.fillna(df.name_y, inplace=True)
                del df['name_y']
            else:
                df = dfreq_cluster
                df['totalFunding'] = ''
                df.rename(columns={'name': 'clusterName'}, inplace=True)
        else:
            if fund_data_cluster:
                df = json_normalize(fund_data_cluster)
                df['revisedRequirements'] = ''
                df.rename(columns={'name': 'clusterName'}, inplace=True)
            else:
                logger.error('No data in %s!' % funding_url)
                continue

        df.rename(columns={'id': 'clusterCode'}, inplace=True)
        df = drop_columns_except(df, plan_columns_to_keep)
        remove_nonenan(df, 'clusterCode')
        if fund_data_cluster is None:
            shared_funding = None
        else:
            shared_funding = data['report3']['fundingTotals']['objects'][0]['totalBreakdown']['sharedFunding']
        if shared_funding:
            row = {'clusterCode': '', 'clusterName': 'zzz', 'revisedRequirements': '', 'totalFunding': shared_funding}
            df.loc[len(df)] = row
        df['id'] = planid

        combined = combined.append(df, ignore_index=True)

    if file_to_upload_funddet:
        dffunddet['destPlanCode'] = dffunddet.destPlanId.map(planidcodemapping).fillna(dffunddet.destPlanCode)
        dffunddet.to_csv(file_to_upload_funddet, encoding='utf-8', index=False, date_format='%Y-%m-%d')
    hxldffundreq.to_csv(file_to_upload_hxldffundreq, encoding='utf-8', index=False, date_format='%Y-%m-%d')

    if len(combined) == 0:
        logger.warning('No cluster data available')
        return dataset, showcase, None

    df = combined.merge(dffundreq, on='id')
    df.rename(columns={'name_x': 'name', 'revisedRequirements_x': 'revisedRequirements', 'totalFunding_x': 'totalFunding'}, inplace=True)
    df = drop_columns_except(df, cluster_columns_to_keep)
    df['percentFunded'] = (to_numeric(df.totalFunding) / to_numeric(df.revisedRequirements) * 100).astype(str)
    remove_fractions(df, 'revisedRequirements')
    remove_nonenan(df, 'revisedRequirements')
    remove_fractions(df, 'totalFunding')
    remove_nonenan(df, 'totalFunding')
    remove_fractions(df, 'percentFunded')
    remove_nonenan(df, 'percentFunded')
    df['id'] = df.id.astype(str)
    remove_fractions(df, 'id')
    remove_nonenan(df, 'id')
    remove_fractions(df, 'clusterCode')
    remove_nonenan(df, 'clusterCode')
    df.sort_values(['endDate', 'name', 'clusterName'], ascending=[False, True, True], inplace=True)
    df['clusterName'].replace('zzz', 'Shared Funding', inplace=True)
    s = df['clusterName']
    hxl_resource = None
    filename = 'fts_requirements_funding_cluster_%s.csv' % countryiso.lower()
    resource_name = filename.lower()
    if not s[~s.isin(['Shared Funding', 'Multi-sector', 'Not specified'])].empty:
        s = df['percentFunded'] == ''
        if not s[~s.isin([True])].empty:
            hxl_resource = resource_name
    df = hxlate(df, hxl_names)
    df.rename(index=str, columns=rename_columns, inplace=True)

    file_to_upload = join(folder, filename)
    df.to_csv(file_to_upload, encoding='utf-8', index=False, date_format='%Y-%m-%d')

    resource_data = {
        'name': resource_name,
        'description': 'FTS Annual Requirements and Funding Data by Cluster for %s' % countryname,
        'format': 'csv'
    }
    resource = Resource(resource_data)
    resource.set_file_to_upload(file_to_upload)
    dataset.add_update_resource(resource)

    return dataset, showcase, hxl_resource


def generate_resource_view(dataset):
    resourceview = ResourceView({'resource_id': dataset.get_resource()['id']})
    resourceview.update_from_yaml()
    return resourceview
