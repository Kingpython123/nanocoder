from blog.post import Post


def test_post_slug():
    assert Post("Hello World!").slug == "hello_world"
