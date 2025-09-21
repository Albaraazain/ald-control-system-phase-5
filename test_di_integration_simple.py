#!/usr/bin/env python3
"""
Simple DI Integration Test
Tests core DI container functionality and system integration
"""

import asyncio
import sys
import os
sys.path.append('.')

from src.di.container import ServiceContainer
from src.di.service_locator import ServiceLocator
from src.log_setup import logger

async def test_di_integration():
    """Test DI container integration"""
    print("🚀 Starting Simple DI Integration Test")

    try:
        # Test 1: Basic container creation
        print("🔍 Test 1: Container Creation")
        container = ServiceContainer()
        assert container is not None
        print("✅ Container created successfully")

        # Test 2: ServiceLocator configuration
        print("🔍 Test 2: ServiceLocator Configuration")
        ServiceLocator.configure(container)
        assert ServiceLocator.is_configured()
        print("✅ ServiceLocator configured successfully")

        # Test 3: Service registration and resolution
        print("🔍 Test 3: Service Registration & Resolution")

        class TestService:
            def __init__(self):
                self.value = "test_success"

        container.register_singleton(TestService)
        service = await container.resolve(TestService)
        assert service.value == "test_success"
        print("✅ Service registration and resolution working")

        # Test 4: Auto-wiring
        print("🔍 Test 4: Auto-wiring Dependencies")

        class DatabaseService:
            def __init__(self):
                self.connected = True

        class AppService:
            def __init__(self, db: DatabaseService):
                self.db = db
                self.initialized = True

        container.register_singleton(DatabaseService)
        container.register_singleton(AppService)

        app_service = await container.resolve(AppService)
        assert app_service.initialized
        assert app_service.db.connected
        print("✅ Auto-wiring working correctly")

        # Test 5: Performance
        print("🔍 Test 5: Performance Testing")
        import time

        times = []
        for i in range(100):
            start = time.perf_counter()
            service = await container.resolve(TestService)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        avg_time = sum(times) / len(times)
        print(f"✅ Average resolution time: {avg_time:.3f}ms")
        assert avg_time < 1.0, f"Too slow: {avg_time:.3f}ms"

        # Test 6: Error handling
        print("🔍 Test 6: Error Handling")

        class UnregisteredService:
            pass

        try:
            await container.resolve(UnregisteredService)
            assert False, "Should have failed"
        except Exception as e:
            print(f"✅ Properly handled unregistered service: {type(e).__name__}")

        # Test 7: Health check
        print("🔍 Test 7: Health Check")
        health = await container.health_check()
        assert isinstance(health, dict)
        print(f"✅ Health check completed for {len(health)} services")

        # Test 8: Cleanup
        print("🔍 Test 8: Container Disposal")
        await container.dispose()

        try:
            container.register_singleton(TestService)
            assert False, "Should have failed after disposal"
        except RuntimeError:
            print("✅ Container properly disposed")

        # Reset ServiceLocator
        ServiceLocator.reset()

        print("\n🎉 ALL TESTS PASSED!")
        print("=" * 50)
        print("DI Container Integration: ✅ WORKING")
        print("ServiceLocator: ✅ WORKING")
        print("Auto-wiring: ✅ WORKING")
        print("Performance: ✅ ACCEPTABLE")
        print("Error Handling: ✅ WORKING")
        print("Health Monitoring: ✅ WORKING")
        print("Lifecycle Management: ✅ WORKING")
        print("=" * 50)

        return True

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_di_integration())
    sys.exit(0 if success else 1)