import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine

from app.db import create_session_factory
from app.models.site_account import SiteAccount
from tests.conftest import create_test_client, make_sqlite_url


def test_create_source_returns_201_and_payload(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create.db"))

    response = client.post(
        "/api/sources",
        json={
            "name": "NGA 热点帖",
            "site_name": "NGA",
            "entry_url": "https://example.com/nga",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游", "版号"],
            "exclude_keywords": ["水贴"],
            "max_items": 30,
            "enabled": True,
            "collection_strategy": "bilibili_site_search",
            "search_keyword": "游戏",
            "source_group": "domestic",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "NGA 热点帖"
    assert data["site_name"] == "NGA"
    assert data["fetch_mode"] == "http"
    assert data["list_selector"] == ".topic"
    assert data["include_keywords"] == ["新游", "版号"]
    assert data["collection_strategy"] == "bilibili_site_search"
    assert data["search_keyword"] == "游戏"
    assert data["source_group"] == "domestic"


def test_create_source_returns_account_id_when_bound(tmp_path) -> None:
    db_url = make_sqlite_url(tmp_path, "create-source-account.db")
    client = create_test_client(db_url)
    engine = create_engine(db_url, future=True)
    factory = create_session_factory(engine=engine)
    account_id = uuid4()
    with factory() as session:
        session.add(
            SiteAccount(
                id=account_id,
                platform="bilibili",
                account_key="creator-a",
                display_name="账号A",
                enabled=True,
                is_default=False,
            )
        )
        session.commit()

    response = client.post(
        "/api/sources",
        json={
            "name": "B站UP主来源",
            "site_name": "Bilibili",
            "entry_url": "https://space.bilibili.com/20411266",
            "fetch_mode": "playwright",
            "parser_type": None,
            "include_keywords": [],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "collection_strategy": "bilibili_profile_videos_recent",
            "search_keyword": None,
            "source_group": "domestic",
            "account_id": str(account_id),
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["account_id"] == str(account_id)


def test_list_sources_returns_created_source(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "list.db"))
    client.post(
        "/api/sources",
        json={
            "name": "NGA 热点帖",
            "site_name": "NGA",
            "entry_url": "https://example.com/nga",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": ["水贴"],
            "max_items": 30,
            "enabled": True,
            "source_group": "domestic",
        },
    )

    response = client.get("/api/sources")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "NGA 热点帖"
    assert data[0]["title_selector"] == ".topic-link"
    assert data[0]["collection_strategy"] == "generic_css"
    assert data[0]["search_keyword"] is None
    assert data[0]["source_group"] == "domestic"


def test_update_source_persists_changes(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "update.db"))
    created = client.post(
        "/api/sources",
        json={
            "name": "NGA 热点帖",
            "site_name": "NGA",
            "entry_url": "https://example.com/nga",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": ["水贴"],
            "max_items": 30,
            "enabled": True,
            "collection_strategy": "generic_css",
            "search_keyword": None,
            "source_group": "domestic",
        },
    ).json()

    response = client.put(
        f"/api/sources/{created['id']}",
        json={
            "name": "NGA 新热帖",
            "max_items": 50,
            "enabled": False,
            "include_keywords": ["手游", "版号"],
            "collection_strategy": "youtube_channel_recent",
            "search_keyword": "",
            "source_group": "overseas",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "NGA 新热帖"
    assert data["max_items"] == 50
    assert data["enabled"] is False
    assert data["include_keywords"] == ["手游", "版号"]
    assert data["collection_strategy"] == "youtube_channel_recent"
    assert data["search_keyword"] == ""
    assert data["source_group"] == "overseas"


def test_delete_source_removes_record(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "delete.db"))
    created = client.post(
        "/api/sources",
        json={
            "name": "NGA 热点帖",
            "site_name": "NGA",
            "entry_url": "https://example.com/nga",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": ["水贴"],
            "max_items": 30,
            "enabled": True,
            "source_group": "domestic",
        },
    ).json()

    delete_response = client.delete(f"/api/sources/{created['id']}")
    list_response = client.get("/api/sources")

    assert delete_response.status_code == 204
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_create_source_from_form_supports_collection_strategy_and_search_keyword(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form.db"))

    response = client.post(
        "/api/sources/form",
        data={
            "name": "B站-游戏-今日搜索",
            "site_name": "Bilibili",
            "entry_url": "https://www.bilibili.com/",
            "fetch_mode": "playwright",
            "parser_type": "generic_css",
            "max_items": "30",
            "collection_strategy": "bilibili_site_search",
            "search_keyword": "游戏",
            "source_group": "domestic",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/sources"

    list_response = client.get("/api/sources")
    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["name"] == "B站-游戏-今日搜索"
    assert data[0]["collection_strategy"] == "bilibili_site_search"
    assert data[0]["search_keyword"] == "游戏"
    assert data[0]["source_group"] == "domestic"


def test_create_source_from_form_requires_source_group(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form-missing-group.db"))

    response = client.post(
        "/api/sources/form",
        data={
            "entry_url": "https://www.youtube.com/@ElectronicArts",
            "max_items": "10",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "source_group" in response.text


def test_create_source_from_form_invalid_collection_strategy_returns_422(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form-invalid-strategy.db"))

    response = client.post(
        "/api/sources/form",
        data={
            "name": "非法策略",
            "entry_url": "https://www.bilibili.com/",
            "fetch_mode": "playwright",
            "parser_type": "generic_css",
            "max_items": "30",
            "source_group": "domestic",
            "collection_strategy": "unknown_strategy",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "collection_strategy" in response.text


def test_create_source_from_form_invalid_max_items_returns_422(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form-invalid-max.db"))

    response = client.post(
        "/api/sources/form",
        data={
            "name": "非法数量",
            "entry_url": "https://www.bilibili.com/",
            "fetch_mode": "playwright",
            "parser_type": "generic_css",
            "max_items": "not-a-number",
            "source_group": "domestic",
            "collection_strategy": "generic_css",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "max_items" in response.text


def test_create_source_from_form_rejects_multipart_form_data(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form-multipart.db"))

    response = client.post(
        "/api/sources/form",
        files={
            "name": (None, "multipart 来源"),
            "entry_url": (None, "https://www.bilibili.com/"),
            "fetch_mode": (None, "playwright"),
            "parser_type": (None, "generic_css"),
            "max_items": (None, "30"),
            "source_group": (None, "domestic"),
            "collection_strategy": (None, "generic_css"),
        },
        follow_redirects=False,
    )

    assert response.status_code == 415
    assert "application/x-www-form-urlencoded" in response.text


def test_list_sources_allows_unknown_collection_strategy_value(tmp_path) -> None:
    db_path = tmp_path / "list-unknown-strategy.db"
    client = create_test_client(f"sqlite:///{db_path.as_posix()}")

    client.post(
        "/api/sources",
        json={
            "name": "历史来源",
            "site_name": "Legacy",
            "entry_url": "https://example.com/legacy",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": [],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "collection_strategy": "generic_css",
            "search_keyword": None,
        },
    )

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE sources SET collection_strategy = ?", ("legacy_custom",))
        conn.commit()
    finally:
        conn.close()

    list_response = client.get("/api/sources")
    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["collection_strategy"] == "legacy_custom"

def test_create_source_from_form_infers_bilibili_profile_video_defaults_from_url(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form-bilibili-profile-simple.db"))

    response = client.post(
        "/api/sources/form",
        data={
            "entry_url": "https://space.bilibili.com/20411266?spm_id_from=333.1387.follow.user_card.click",
            "max_items": "12",
            "source_group": "domestic",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    list_response = client.get("/api/sources")
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["name"] == "B站UP-20411266-视频投稿"
    assert data[0]["site_name"] == "Bilibili"
    assert data[0]["fetch_mode"] == "playwright"
    assert data[0]["collection_strategy"] == "bilibili_profile_videos_recent"
    assert data[0]["search_keyword"] is None
    assert data[0]["source_group"] == "domestic"

def test_create_source_from_form_infers_bilibili_defaults_from_url(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form-bilibili-simple.db"))

    response = client.post(
        "/api/sources/form",
        data={
            "entry_url": "https://www.bilibili.com/",
            "search_keyword": "游戏",
            "max_items": "30",
            "source_group": "domestic",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    list_response = client.get("/api/sources")
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["name"] == "B站-游戏-站内搜索"
    assert data[0]["site_name"] == "Bilibili"
    assert data[0]["fetch_mode"] == "playwright"
    assert data[0]["collection_strategy"] == "bilibili_site_search"
    assert data[0]["search_keyword"] == "游戏"
    assert data[0]["source_group"] == "domestic"


def test_create_source_from_form_infers_youtube_defaults_from_url(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form-youtube-simple.db"))

    response = client.post(
        "/api/sources/form",
        data={
            "entry_url": "https://www.youtube.com/@ElectronicArts",
            "max_items": "10",
            "source_group": "overseas",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    list_response = client.get("/api/sources")
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["name"] == "YouTube-ElectronicArts"
    assert data[0]["site_name"] == "YouTube"
    assert data[0]["fetch_mode"] == "playwright"
    assert data[0]["collection_strategy"] == "youtube_channel_recent"
    assert data[0]["search_keyword"] is None
    assert data[0]["source_group"] == "overseas"


def test_create_source_from_form_requires_keyword_for_bilibili_site_search(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form-bilibili-keyword.db"))

    response = client.post(
        "/api/sources/form",
        data={
            "entry_url": "https://www.bilibili.com/",
            "max_items": "30",
            "source_group": "domestic",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "search_keyword" in response.text


def test_create_source_from_form_infers_x_defaults_from_url(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "create-form-x-simple.db"))

    response = client.post(
        "/api/sources/form",
        data={
            "entry_url": "https://x.com/PUBG",
            "max_items": "10",
            "source_group": "overseas",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    list_response = client.get("/api/sources")
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["name"] == "X-PUBG"
    assert data[0]["site_name"] == "X"
    assert data[0]["fetch_mode"] == "playwright"
    assert data[0]["collection_strategy"] == "x_profile_recent"
    assert data[0]["search_keyword"] is None
    assert data[0]["source_group"] == "overseas"

def test_delete_source_from_form_redirects_and_removes_record(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "delete-form.db"))
    created = client.post(
        "/api/sources",
        json={
            "name": "待删除来源",
            "site_name": "NGA",
            "entry_url": "https://example.com/nga-delete",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
        },
    ).json()

    delete_response = client.post(f"/api/sources/{created['id']}/delete", follow_redirects=False)
    list_response = client.get("/api/sources")

    assert delete_response.status_code == 303
    assert delete_response.headers["location"] == "/sources"
    assert list_response.status_code == 200
    assert list_response.json() == []



DELETE_SOURCE_HTML = """
<html>
  <body>
    <ul class='topics'>
      <li class='topic'>
        <a class='topic-link' href='https://example.com/post-1'>重磅新游版号过审</a>
        <span class='topic-time'>2026-03-24 08:00</span>
      </li>
    </ul>
  </body>
</html>
""".strip()


def test_delete_source_after_successful_collection_still_works(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "true")
    html_path = Path(tmp_path) / 'topics.html'
    html_path.write_text(DELETE_SOURCE_HTML, encoding='utf-8')
    client = create_test_client(make_sqlite_url(tmp_path, 'delete-after-job.db'))
    created = client.post(
        '/api/sources',
        json={
            'name': '已采集来源',
            'site_name': 'Local',
            'entry_url': html_path.resolve().as_uri(),
            'fetch_mode': 'http',
            'parser_type': 'generic_css',
            'list_selector': '.topic',
            'title_selector': '.topic-link',
            'link_selector': '.topic-link',
            'meta_selector': '.topic-time',
            'include_keywords': ['新游'],
            'exclude_keywords': [],
            'max_items': 30,
            'enabled': True,
        },
    ).json()

    run_response = client.post('/jobs/run', follow_redirects=False)
    job_id = run_response.headers['location'].rsplit('/', 1)[-1]
    for _ in range(20):
        body = client.get(f'/api/jobs/{job_id}').json()
        if body['status'] == 'success':
            break
        time.sleep(0.05)
    else:
        raise AssertionError(f'job {job_id} did not finish successfully')

    delete_response = client.delete(f"/api/sources/{created['id']}")
    list_response = client.get('/api/sources')

    assert delete_response.status_code == 204
    assert list_response.status_code == 200
    assert list_response.json() == []
