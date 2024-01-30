import sys
import traceback
import asyncio
import boto3

from yaml import safe_load
from time import time

CF_ID = 'E350YQ1S7SVOQT'


def parse_yaml(file: str):
    with open(file, 'r') as f:
        values = safe_load(f)
    return values


class CloudFrontWrapper:
    def __init__(self, cloudfront_client):
        """
        :param cloudfront_client: A Boto3 CloudFront client
        """
        self.cloudfront_client = cloudfront_client

    @staticmethod
    def _confirm_response(response_metadata: dict, msg: str = '') -> None:
        response_code = response_metadata.get('ResponseMetadata').get('HTTPStatusCode')

        if response_code not in [200, 201, 204]:
            print(f'Response from AWS backend not successful, returned code: {response_code}')
        else:
            print(f'{msg} -- {response_code} -- Success!')
        return

    def _fetch_distribution_config(self, distribution_id: str) -> dict:
        try:
            distribution_config_response = self.cloudfront_client.get_distribution_config(Id=distribution_id)
        except self.cloudfront_client.exceptions.NoSuchDistribution:
            print(traceback.format_exc())
            print(f'The provided CloudFront distribution "{distribution_id}" could not be found!')
            sys.exit(1)
        except self.cloudfront_client.exceptions.AccessDenied:
            print(traceback.format_exc())
            print('Please check the executor permissions, access has been DENIED!')
            sys.exit(1)

        self._confirm_response(distribution_config_response, 'FETCH')
        return distribution_config_response

    def _update_distribution_config(self, distribution_id: str, origin: str) -> None:
        distribution_response = self._fetch_distribution_config(distribution_id)
        distribution_config = distribution_response.get('DistributionConfig')
        distribution_etag = distribution_response.get('ETag')

        distribution_config['Origins'] = {
            'Quantity': 1,
            'Items': [{'Id': origin,
                       'DomainName': origin,
                       'OriginPath': '',
                       'CustomHeaders': {'Quantity': 0},
                       'S3OriginConfig': {'OriginAccessIdentity': ''},
                       'ConnectionAttempts': 3,
                       'ConnectionTimeout': 10,
                       'OriginShield': {'Enabled': False},
                       'OriginAccessControlId': ''}]
        }
        distribution_config['DefaultCacheBehavior']['TargetOriginId'] = origin

        try:
            distribution_update_response = self.cloudfront_client.update_distribution(
                DistributionConfig=distribution_config,
                Id=distribution_id,
                IfMatch=distribution_etag,
            )
        except self.cloudfront_client.exceptions.NoSuchDistribution:
            print(traceback.format_exc())
            print(f'The provided CloudFront distribution "{distribution_id}" could not be found!')
            sys.exit(1)
        except self.cloudfront_client.exceptions.AccessDenied:
            print(traceback.format_exc())
            print('Please check the executor permissions, access has been DENIED!')
            sys.exit(1)

        self._confirm_response(distribution_update_response, 'UPDATE CONFIG')
        print('CloudFront distribution config updated!')

    async def _clear_distribution_cache(self, distribution_id: str):
        try:
            invalidation_response = self.cloudfront_client.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': 1,
                        'Items': ['/*']
                    },
                    'CallerReference': str(time()).replace(',', '')  # Using this as a unique identifier
                }
            )
            self._confirm_response(invalidation_response, 'CACHE INVALIDATION')
        except self.cloudfront_client.exceptions.NoSuchDistribution:
            print(traceback.format_exc())
            print(f'The provided CloudFront distribution "{distribution_id}" could not be found!')
            sys.exit(1)
        except self.cloudfront_client.exceptions.AccessDenied:
            print(traceback.format_exc())
            print('Please check the executor permissions, access has been DENIED!')
            sys.exit(1)

        return invalidation_response

    async def setup(self, distribution_id: str, origins: str) -> None:
        await self._clear_distribution_cache(distribution_id)
        self._update_distribution_config(distribution_id, origins)
        print('--------- \nCloudFront origins failover completed successfully! \n---------')


if __name__ == '__main__':
    # Parse the YAML file to get the needed values
    v = parse_yaml('values.yaml')

    # Initialize the Boto3 client for CloudFront
    client = boto3.client('cloudfront')

    # Initialize the resource wrapper that will handle operations
    CFWrapper = CloudFrontWrapper(client)

    # Run fail over setup
    asyncio.run(CFWrapper.setup(CF_ID, v.get('S3Origin2')))
