import pytest
import asyncio
import sys
import json
from unittest.mock import AsyncMock, MagicMock, patch

# Mock rembg before importing the worker to prevent ONNX weight downloads / slow boot
mock_rembg = MagicMock()
sys.modules['rembg'] = mock_rembg

mock_firecrawl = MagicMock()
sys.modules['firecrawl'] = mock_firecrawl

from app.workers.worker_extract import phase1_extract, _compute_confidence, _suggest_motion

@pytest.fixture
def mock_ctx():
    """Minimal ARQ ctx dict with all external dependencies mocked."""
    
    # DB pool: conn.fetchrow, conn.execute both async
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value = acquire_ctx

    # Redis DB0: lpush + expire are async
    mock_redis = AsyncMock()

    # R2 client: get_object and put_object run via asyncio.to_thread (sync boto3 calls)
    mock_r2 = MagicMock()

    # Gateway: route is async
    mock_gateway = AsyncMock()

    return {
        "db_pool":   mock_pool,
        "redis_db0": mock_redis,
        "r2_client": mock_r2,
        "gateway":   mock_gateway,
        "_conn":     mock_conn,   # expose for assertions
    }

def _vision_result(category="d2c_beauty", shape="tall_bottle"):
    return {
        "product_name":  "Test Product",
        "category":      category,
        "price_inr":     499.0,
        "key_features":  ["feature_a", "feature_b"],
        "color_palette": ["#FF0000", "#FFFFFF"],
        "shape":         shape,
    }

def _make_rgba_pil(fg_ratio=0.6, soft_ratio=0.1, size=(100, 100)):
    """
    Creates a synthetic PIL RGBA image for _compute_confidence testing.
    fg_ratio: fraction of pixels with alpha > 128
    soft_ratio: fraction of pixels with 10 < alpha < 245 (soft edges)
    """
    import numpy as np
    from PIL import Image
    total = size[0] * size[1]
    alpha = np.zeros(total, dtype=np.uint8)
    fg_count = int(total * fg_ratio)
    alpha[:fg_count] = 255          # hard foreground
    soft_count = int(total * soft_ratio)
    alpha[fg_count:fg_count+soft_count] = 128  # soft edges (>10, <245)
    alpha_2d = alpha.reshape(size)
    rgba = np.zeros((*size, 4), dtype=np.uint8)
    rgba[:, :, 3] = alpha_2d
    return Image.fromarray(rgba, 'RGBA')

@pytest.mark.asyncio
@patch('app.workers.worker_extract.remove')
@patch('app.workers.worker_extract.asyncio.to_thread', new_callable=AsyncMock)
@patch('app.workers.worker_extract.httpx.AsyncClient')
@patch('app.workers.worker_extract.os.environ', {"FIRECRAWL_API_KEY": "test", "R2_BUCKET_NAME": "test", "R2_PUBLIC_BASE_URL": "http://cdn"})
async def test_happy_path_url_source(MockAsyncClient, mock_to_thread, mock_remove, mock_ctx):
    # We patch inside the function instead of class decorator to handle FirecrawlApp properly, 
    # since it's imported locally in the original file
    with patch('firecrawl.FirecrawlApp', create=True) as MockFirecrawl:
        mock_conn = mock_ctx["_conn"]
        mock_conn.fetchrow.return_value = {
            "gen_id": "test_1",
            "status": "queued",
            "source_url": "http://example.com",
            "source_image_r2_key": None,
            "user_id": "u1"
        }
        mock_conn.execute.return_value = "UPDATE 1"
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = MagicMock(content=b"x" * 100)
        mock_client_instance.get.return_value.raise_for_status = MagicMock()
        MockAsyncClient.return_value.__aenter__.return_value = mock_client_instance
        
        async def side_effect_to_thread(func, *args, **kwargs):
            if 'scrape_url' in str(func) or getattr(func, '__name__', '') == 'scrape_url':
                return {"metadata": {"og:image": "http://img.example.com/p.jpg"}}
            if 'put_object' in str(func) or getattr(func, '__name__', '') == 'put_object':
                return {}
            if 'get_object' in str(func) or getattr(func, '__name__', '') == 'get_object':
                return {"Body": MagicMock(read=lambda: b"x"*100)}
            return _make_rgba_pil(fg_ratio=0.95, soft_ratio=0.02)
            
        mock_to_thread.side_effect = side_effect_to_thread
        
        mock_ctx["gateway"].route.return_value = _vision_result(category='d2c_beauty', shape='tall_bottle')
        
        await phase1_extract(mock_ctx, gen_id="test_1")
        
        execute_calls = mock_conn.execute.call_args_list
        assert any("status = 'extracting'" in call[0][0] for call in execute_calls)
        assert any("status                  = 'brief_ready'" in call[0][0] for call in execute_calls)
        assert not any("pre_topup_status" in call[0][0] for call in execute_calls)
        
        assert mock_ctx["redis_db0"].lpush.call_count >= 2
        
        phase_complete_call = [call for call in mock_ctx["redis_db0"].lpush.call_args_list if "phase_complete" in call[0][1]]
        assert len(phase_complete_call) > 0
        payload = json.loads(phase_complete_call[0][0][1])
        assert "confidence_score" in payload
        assert isinstance(payload["confidence_score"], float)
        
        brief_ready_call = [call for call in execute_calls if "status                  = 'brief_ready'" in call[0][0]][0]
        assert brief_ready_call[0][4] is not None  # agent_motion_suggestion

@pytest.mark.asyncio
@patch('app.workers.worker_extract.remove')
@patch('app.workers.worker_extract.asyncio.to_thread', new_callable=AsyncMock)
@patch('app.workers.worker_extract.os.environ', {"R2_BUCKET_NAME": "test", "R2_PUBLIC_BASE_URL": "http://cdn"})
async def test_happy_path_r2_source(mock_to_thread, mock_remove, mock_ctx):
    mock_conn = mock_ctx["_conn"]
    mock_conn.fetchrow.return_value = {
        "gen_id": "test_1",
        "status": "queued",
        "source_url": None,
        "source_image_r2_key": "uploads/user1/gen1.png",
        "user_id": "u1"
    }
    mock_conn.execute.return_value = "UPDATE 1"
    
    async def side_effect_to_thread(func, *args, **kwargs):
        if 'get_object' in str(func) or getattr(func, '__name__', '') == 'get_object':
            return {"Body": MagicMock(read=lambda: b"x"*100)}
        if 'put_object' in str(func) or getattr(func, '__name__', '') == 'put_object':
            return {}
        return _make_rgba_pil(fg_ratio=0.95, soft_ratio=0.02)
        
    mock_to_thread.side_effect = side_effect_to_thread
    
    mock_ctx["gateway"].route.return_value = _vision_result(category='electronics')
    
    await phase1_extract(mock_ctx, gen_id="test_1")
    
    execute_calls = mock_conn.execute.call_args_list
    assert any("brief_ready" in call[0][0] for call in execute_calls)
    assert not any("failed_category" in call[0][0] for call in execute_calls)
    assert 'firecrawl' not in sys.modules or not hasattr(sys.modules.get('firecrawl', None), 'FirecrawlApp') # or it wasn't called

@pytest.mark.asyncio
@patch('app.workers.worker_extract.asyncio.to_thread', new_callable=AsyncMock)
@patch('app.workers.worker_extract.httpx.AsyncClient')
@patch('app.workers.worker_extract.os.environ', {"FIRECRAWL_API_KEY": "test"})
async def test_scraped_image_too_large(MockAsyncClient, mock_to_thread, mock_ctx):
    with patch('firecrawl.FirecrawlApp', create=True) as MockFirecrawl:
        mock_conn = mock_ctx["_conn"]
        mock_conn.fetchrow.return_value = {
            "gen_id": "test_1",
            "status": "queued",
            "source_url": "http://example.com",
            "source_image_r2_key": None,
            "user_id": "u1"
        }
        mock_conn.execute.return_value = "UPDATE 1"
        
        async def side_effect_to_thread(func, *args, **kwargs):
            if 'scrape_url' in str(func) or getattr(func, '__name__', '') == 'scrape_url':
                return {"metadata": {"og:image": "http://img.example.com/p.jpg"}}
            return MagicMock()
        mock_to_thread.side_effect = side_effect_to_thread
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = MagicMock(content=b"x" * (16 * 1024 * 1024))
        mock_client_instance.get.return_value.raise_for_status = MagicMock()
        MockAsyncClient.return_value.__aenter__.return_value = mock_client_instance
        
        await phase1_extract(mock_ctx, gen_id="test_1")
        
        execute_calls = mock_conn.execute.call_args_list
        assert any("failed_category" in call[0][0] and "ECM-001" in call[0][1] for call in execute_calls)
        assert not any("brief_ready" in call[0][0] for call in execute_calls)
        
        push_calls = mock_ctx["redis_db0"].lpush.call_args_list
        assert any('"status": "failed_category"' in call[0][1] and '"ecm": "ECM-001"' in call[0][1] for call in push_calls)
        
        assert mock_ctx["gateway"].route.call_count == 0

@pytest.mark.asyncio
@patch('app.workers.worker_extract.remove')
@patch('app.workers.worker_extract.asyncio.to_thread', new_callable=AsyncMock)
@patch('app.workers.worker_extract.httpx.AsyncClient')
@patch('app.workers.worker_extract.os.environ', {"FIRECRAWL_API_KEY": "test", "R2_BUCKET_NAME": "test", "R2_PUBLIC_BASE_URL": "http://cdn"})
async def test_red_zone_category(MockAsyncClient, mock_to_thread, mock_remove, mock_ctx):
    with patch('firecrawl.FirecrawlApp', create=True) as MockFirecrawl:
        mock_conn = mock_ctx["_conn"]
        mock_conn.fetchrow.return_value = {
            "gen_id": "test_1",
            "status": "queued",
            "source_url": "http://example.com",
            "source_image_r2_key": None,
            "user_id": "u1"
        }
        mock_conn.execute.return_value = "UPDATE 1"
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = MagicMock(content=b"x" * 100)
        mock_client_instance.get.return_value.raise_for_status = MagicMock()
        MockAsyncClient.return_value.__aenter__.return_value = mock_client_instance
        
        async def side_effect_to_thread(func, *args, **kwargs):
            if 'scrape_url' in str(func) or getattr(func, '__name__', '') == 'scrape_url':
                return {"metadata": {"og:image": "http://img.example.com/p.jpg"}}
            if 'put_object' in str(func) or getattr(func, '__name__', '') == 'put_object':
                return {}
            return _make_rgba_pil(fg_ratio=0.95, soft_ratio=0.02)
        mock_to_thread.side_effect = side_effect_to_thread
        
        mock_ctx["gateway"].route.return_value = _vision_result(category='alcohol')  # Red zone
        
        await phase1_extract(mock_ctx, gen_id="test_1")
        
        execute_calls = mock_conn.execute.call_args_list
        assert any("failed_category" in call[0][0] and "ECM-001" in call[0][1] for call in execute_calls)
        assert not any("brief_ready" in call[0][0] for call in execute_calls)

@pytest.mark.asyncio
@patch('app.workers.worker_extract.remove')
@patch('app.workers.worker_extract.asyncio.to_thread', new_callable=AsyncMock)
@patch('app.workers.worker_extract.httpx.AsyncClient')
@patch('app.workers.worker_extract.os.environ', {"FIRECRAWL_API_KEY": "test", "R2_BUCKET_NAME": "test", "R2_PUBLIC_BASE_URL": "http://cdn"})
async def test_confidence_below_090_no_motion_suggestion(MockAsyncClient, mock_to_thread, mock_remove, mock_ctx):
    with patch('firecrawl.FirecrawlApp', create=True) as MockFirecrawl:
        mock_conn = mock_ctx["_conn"]
        mock_conn.fetchrow.return_value = {
            "gen_id": "test_1",
            "status": "queued",
            "source_url": "http://example.com",
            "source_image_r2_key": None,
            "user_id": "u1"
        }
        mock_conn.execute.return_value = "UPDATE 1"
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = MagicMock(content=b"x" * 100)
        mock_client_instance.get.return_value.raise_for_status = MagicMock()
        MockAsyncClient.return_value.__aenter__.return_value = mock_client_instance
        
        async def side_effect_to_thread(func, *args, **kwargs):
            if 'scrape_url' in str(func) or getattr(func, '__name__', '') == 'scrape_url':
                return {"metadata": {"og:image": "http://img.example.com/p.jpg"}}
            if 'put_object' in str(func) or getattr(func, '__name__', '') == 'put_object':
                return {}
            return _make_rgba_pil(fg_ratio=0.5, soft_ratio=0.4)
        mock_to_thread.side_effect = side_effect_to_thread
        
        mock_ctx["gateway"].route.return_value = _vision_result(category='d2c_beauty')
        
        await phase1_extract(mock_ctx, gen_id="test_1")
        
        execute_calls = mock_conn.execute.call_args_list
        brief_ready_call = [call for call in execute_calls if "brief_ready" in call[0][0]][0]
        assert brief_ready_call[0][4] is None

def test_compute_confidence_formula():
    # Case A: all-opaque
    img_a = _make_rgba_pil(fg_ratio=1.0, soft_ratio=0.0)
    res_a = _compute_confidence(img_a)
    assert isinstance(res_a, float)
    assert res_a == 1.0
    
    # Case B: all-transparent
    img_b = _make_rgba_pil(fg_ratio=0.0, soft_ratio=0.0)
    res_b = _compute_confidence(img_b)
    assert isinstance(res_b, float)
    assert res_b == 0.0
    
    # Case C: mixed
    img_c = _make_rgba_pil(fg_ratio=0.8, soft_ratio=0.1, size=(1000, 1000))
    res_c = _compute_confidence(img_c)
    expected = 0.8 * (1.0 - 0.1 * 0.4)
    assert abs(res_c - expected) < 0.05
    assert 0.0 <= res_c <= 1.0

@pytest.mark.asyncio
async def test_skips_if_not_queued(mock_ctx):
    mock_conn = mock_ctx["_conn"]
    mock_conn.fetchrow.return_value = {
        "gen_id": "test_1",
        "status": "extracting",
        "source_url": "http://example.com",
        "source_image_r2_key": None,
        "user_id": "u1"
    }
    
    await phase1_extract(mock_ctx, gen_id="test_1")
    
    assert mock_conn.execute.call_count == 0
    assert mock_ctx["gateway"].route.call_count == 0

@pytest.mark.asyncio
@patch('app.workers.worker_extract.os.environ', {"FIRECRAWL_API_KEY": "test"})
async def test_unhandled_exception_sets_failed_category(mock_ctx):
    with patch('firecrawl.FirecrawlApp', create=True) as MockFirecrawl:
        mock_conn = mock_ctx["_conn"]
        mock_conn.fetchrow.return_value = {
            "gen_id": "test_1",
            "status": "queued",
            "source_url": "http://example.com",
            "source_image_r2_key": None,
            "user_id": "u1"
        }
        mock_conn.execute.return_value = "UPDATE 1"
        
        MockFirecrawl.side_effect = RuntimeError("unexpected crash")
        
        await phase1_extract(mock_ctx, gen_id="test_1")
        
        execute_calls = mock_conn.execute.call_args_list
        assert any("failed_category" in call[0][0] for call in execute_calls)
        assert not any("brief_ready" in call[0][0] for call in execute_calls)
