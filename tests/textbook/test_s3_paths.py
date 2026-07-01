"""Subject-scoped S3 paths for textbook images."""

from ibrary.textbook.s3_paths import (
    textbook_image_s3_key,
    textbook_image_s3_url,
    textbook_images_prefix,
)


def test_textbook_image_paths_use_subject_slug():
    assert textbook_images_prefix(subject_slug="biology") == "biology/textbook-images"
    assert (
        textbook_image_s3_key("bio2e_ch1_sec1_pg28_img0", "jpeg", subject_slug="biology")
        == "biology/textbook-images/bio2e_ch1_sec1_pg28_img0.jpeg"
    )
    assert textbook_image_s3_url(
        "bio2e_ch1_sec1_pg28_img0",
        "jpeg",
        bucket="ibrary-content",
        subject_slug="biology",
    ) == (
        "s3://ibrary-content/biology/textbook-images/bio2e_ch1_sec1_pg28_img0.jpeg"
    )
