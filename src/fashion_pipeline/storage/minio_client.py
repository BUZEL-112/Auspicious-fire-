import io
from datetime import timedelta
from typing import Optional
from minio import Minio
from minio.error import S3Error
from fashion_pipeline.config.settings import settings


class MinIOClient:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: Optional[bool] = None,
    ):
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.access_key = access_key or settings.MINIO_ACCESS_KEY
        self.secret_key = secret_key or settings.MINIO_SECRET_KEY
        self.secure = secure if secure is not None else settings.MINIO_SECURE

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    def ensure_bucket_exists(self, bucket_name: str) -> None:
        if not self.client.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)

    def upload_bytes(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        self.ensure_bucket_exists(bucket_name)
        data_stream = io.BytesIO(data)
        self.client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=data_stream,
            length=len(data),
            content_type=content_type,
        )
        return f"minio://{bucket_name}/{object_name}"

    def download_bytes(self, bucket_name: str, object_name: str) -> bytes:
        response = self.client.get_object(bucket_name, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def generate_presigned_put_url(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta = timedelta(minutes=15),
    ) -> str:
        self.ensure_bucket_exists(bucket_name)
        return self.client.get_presigned_url(
            method="PUT",
            bucket_name=bucket_name,
            object_name=object_name,
            expires=expires,
        )

    def generate_presigned_get_url(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        return self.client.get_presigned_url(
            method="GET",
            bucket_name=bucket_name,
            object_name=object_name,
            expires=expires,
        )


storage_client = MinIOClient()
