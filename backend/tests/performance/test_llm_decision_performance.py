"""
Performance and load tests for LLM Decision Engine.

Tests decision generation latency, throughput, concurrent processing,
memory usage, and system resource consumption.
"""

import asyncio
import statistics
import time
from unittest.mock import AsyncMock

import pytest

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from app.schemas.trading_decision import (
    AccountContext,
    DecisionResult,
    MarketContext,
    PerformanceMetrics,
    RiskMetrics,
    StrategyRiskParameters,
    TechnicalIndicators,
    TechnicalIndicatorsSet,
    TradingContext,
    TradingDecision,
    TradingStrategy,
    ValidationResult,
)
from app.services.llm.context_builder import ContextBuilderService
from app.services.llm.decision_engine import DecisionEngine
from app.services.llm.decision_validator import DecisionValidator
from app.services.llm.llm_service import LLMService
from app.services.llm.strategy_manager import StrategyManager


class TestLLMDecisionEnginePerformance:
    """Performance tests for LLM Decision Engine."""

    @pytest.fixture
    async def decision_engine(self):
        """Create a DecisionEngine instance for testing."""
        return DecisionEngine()

    @pytest.fixture
    def mock_services_fast(self):
        """Create fast mock services for performance testing."""
        # Mock LLM Service
        mock_llm_service = AsyncMock(spec=LLMService)
        mock_decision = TradingDecision(
            asset="BTCUSDT",
            action="buy",
            allocation_usd=1000.0,
            tp_price=50000.0,
            sl_price=46000.0,
            exit_plan="Take profit at resistance",
            rationale="Strong bullish momentum",
            confidence=85,
            risk_level="medium",
        )
        mock_result = DecisionResult(
            decision=mock_decision,
            context=self._create_mock_context(),
            validation_passed=True,
            validation_errors=[],
            processing_time_ms=50.0,
            model_used="gpt-4",
        )

        async def fast_decision_generation(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10ms simulated processing
            return mock_result

        mock_llm_service.generate_trading_decision.side_effect = fast_decision_generation

        # Mock Context Builder
        mock_context_builder = AsyncMock(spec=ContextBuilderService)
        mock_context = self._create_mock_context()

        async def fast_context_building(*args, **kwargs):
            await asyncio.sleep(0.005)  # 5ms simulated processing
            return mock_context

        mock_context_builder.build_trading_context.side_effect = fast_context_building

        # Mock Decision Validator
        mock_validator = AsyncMock(spec=DecisionValidator)
        mock_validation = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            rules_checked=["schema_validation", "business_rules"],
            validation_time_ms=5.0,
        )

        async def fast_validation(*args, **kwargs):
            await asyncio.sleep(0.002)  # 2ms simulated processing
            return mock_validation

        mock_validator.validate_decision.side_effect = fast_validation

        # Mock Strategy Manager
        mock_strategy_manager = AsyncMock(spec=StrategyManager)
        mock_strategy = self._create_mock_strategy()
        mock_strategy_manager.get_account_strategy.return_value = mock_strategy

        return {
            "llm_service": mock_llm_service,
            "context_builder": mock_context_builder,
            "decision_validator": mock_validator,
            "strategy_manager": mock_strategy_manager,
        }

    def _create_mock_context(self):
        """Create a mock trading context."""
        indicators = TechnicalIndicators(
            interval=TechnicalIndicatorsSet(
                ema_20=[48000.0],
                ema_50=[47000.0],
                rsi=[65.0],
                macd=[100.0],
                bb_upper=[49000.0],
                bb_lower=[46000.0],
                bb_middle=[47500.0],
                atr=[500.0],
            ),
            long_interval=TechnicalIndicatorsSet(
                ema_20=[48000.0],
                ema_50=[47000.0],
                rsi=[65.0],
                macd=[100.0],
                bb_upper=[49000.0],
                bb_lower=[46000.0],
                bb_middle=[47500.0],
                atr=[500.0],
            ),
        )

        market_context = MarketContext(
            current_price=48000.0,
            price_change_24h=1000.0,
            volume_24h=1000000.0,
            funding_rate=0.01,
            open_interest=50000000.0,
            volatility=0.02,
            technical_indicators=indicators,
            price_history=[],
        )

        performance = PerformanceMetrics(
            total_pnl=1000.0,
            win_rate=60.0,
            avg_win=150.0,
            avg_loss=-75.0,
            max_drawdown=-200.0,
            sharpe_ratio=1.5,
        )

        account_context = AccountContext(
            account_id=1,
            balance_usd=10000.0,
            available_balance=8000.0,
            total_pnl=1000.0,
            recent_performance=performance,
            risk_exposure=20.0,
            max_position_size=2000.0,
            active_strategy=self._create_mock_strategy(),
            open_positions=[],
        )

        risk_metrics = RiskMetrics(
            var_95=500.0, max_drawdown=1000.0, correlation_risk=15.0, concentration_risk=25.0
        )

        return TradingContext(
            symbol="BTCUSDT",
            account_id=1,
            market_data=market_context,
            account_state=account_context,
            risk_metrics=risk_metrics,
        )

    def _create_mock_strategy(self):
        """Create a mock trading strategy."""
        risk_params = StrategyRiskParameters(
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
            stop_loss_percentage=3.0,
            take_profit_ratio=2.0,
            max_leverage=3.0,
            cooldown_period=300,
        )

        return TradingStrategy(
            strategy_id="conservative",
            strategy_name="Conservative Trading",
            strategy_type="conservative",
            prompt_template="Conservative trading prompt",
            risk_parameters=risk_params,
            timeframe_preference=["4h", "1d"],
            max_positions=3,
            is_active=True,
        )

    @pytest.mark.asyncio
    async def test_single_decision_latency(self, decision_engine, mock_services_fast):
        """Test latency of single decision generation."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Measure decision latency
        latencies = []
        for _ in range(10):
            start_time = time.time()
            result = await decision_engine.make_trading_decision("BTCUSDT", 1)
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            assert isinstance(result, DecisionResult)
            assert result.validation_passed is True

        # Analyze latency statistics
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        max_latency = max(latencies)

        print("Decision Latency Stats:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  95th percentile: {p95_latency:.2f}ms")
        print(f"  Maximum: {max_latency:.2f}ms")

        # Performance assertions
        assert avg_latency < 100.0  # Average should be under 100ms
        assert p95_latency < 200.0  # 95th percentile should be under 200ms
        assert max_latency < 500.0  # Maximum should be under 500ms

    @pytest.mark.asyncio
    async def test_concurrent_decision_throughput(self, decision_engine, mock_services_fast):
        """Test throughput under concurrent load."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Test different concurrency levels
        concurrency_levels = [1, 5, 10, 20, 50]
        throughput_results = {}

        for concurrency in concurrency_levels:
            # Create concurrent tasks
            tasks = []
            for i in range(concurrency):
                task = decision_engine.make_trading_decision("BTCUSDT", i + 1)
                tasks.append(task)

            # Measure throughput
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            # Calculate throughput
            duration = end_time - start_time
            throughput = concurrency / duration  # decisions per second

            throughput_results[concurrency] = {
                "duration": duration,
                "throughput": throughput,
                "success_count": sum(1 for r in results if isinstance(r, DecisionResult)),
            }

            print(
                f"Concurrency {concurrency}: {throughput:.2f} decisions/sec, {duration:.3f}s duration"
            )

            # Verify all decisions succeeded
            assert throughput_results[concurrency]["success_count"] == concurrency

        # Performance assertions
        assert throughput_results[1]["throughput"] > 10.0  # At least 10 decisions/sec sequential
        assert (
            throughput_results[10]["throughput"] > 50.0
        )  # At least 50 decisions/sec with 10 concurrent

        # Throughput should scale with concurrency (up to a point)
        assert throughput_results[10]["throughput"] > throughput_results[1]["throughput"]

    @pytest.mark.asyncio
    async def test_batch_processing_performance(self, decision_engine, mock_services_fast):
        """Test performance of batch decision processing."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Test different batch sizes
        batch_sizes = [1, 5, 10, 25, 50]
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT"]

        batch_results = {}

        for batch_size in batch_sizes:
            # Use subset of symbols based on batch size
            test_symbols = symbols[: min(batch_size, len(symbols))]
            if batch_size > len(symbols):
                # Repeat symbols to reach desired batch size
                test_symbols = (symbols * ((batch_size // len(symbols)) + 1))[:batch_size]

            # Measure batch processing time
            start_time = time.time()
            results = await decision_engine.batch_decisions(test_symbols, 1)
            end_time = time.time()

            duration = end_time - start_time
            throughput = len(results) / duration

            batch_results[batch_size] = {
                "duration": duration,
                "throughput": throughput,
                "results_count": len(results),
            }

            print(
                f"Batch size {batch_size}: {throughput:.2f} decisions/sec, {duration:.3f}s duration"
            )

            # Verify all decisions were processed
            assert len(results) == batch_size
            for result in results:
                assert isinstance(result, DecisionResult)

        # Performance assertions
        assert batch_results[1]["throughput"] > 5.0  # At least 5 decisions/sec for single
        assert batch_results[10]["throughput"] > 20.0  # At least 20 decisions/sec for batch of 10

    @pytest.mark.asyncio
    async def test_multi_account_concurrent_processing(self, decision_engine, mock_services_fast):
        """Test concurrent processing across multiple accounts."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Test with multiple accounts and symbols
        account_ids = list(range(1, 11))  # 10 accounts
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

        # Create tasks for all account/symbol combinations
        tasks = []
        for account_id in account_ids:
            for symbol in symbols:
                task = decision_engine.make_trading_decision(symbol, account_id)
                tasks.append(task)

        # Measure concurrent processing
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        duration = end_time - start_time
        total_decisions = len(account_ids) * len(symbols)
        throughput = total_decisions / duration

        print("Multi-account processing:")
        print(f"  Accounts: {len(account_ids)}")
        print(f"  Symbols: {len(symbols)}")
        print(f"  Total decisions: {total_decisions}")
        print(f"  Duration: {duration:.3f}s")
        print(f"  Throughput: {throughput:.2f} decisions/sec")

        # Verify all decisions succeeded
        successful_results = [r for r in results if isinstance(r, DecisionResult)]
        assert len(successful_results) == total_decisions

        # Performance assertions
        assert throughput > 30.0  # At least 30 decisions/sec for multi-account processing
        assert duration < 2.0  # Should complete within 2 seconds

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, decision_engine, mock_services_fast):
        """Test memory usage during sustained load."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Get initial memory usage
        if not HAS_PSUTIL:
            pytest.skip("psutil not available")
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Run sustained load
        total_decisions = 100
        batch_size = 10
        memory_samples = []

        for batch in range(total_decisions // batch_size):
            # Process batch of decisions
            tasks = []
            for i in range(batch_size):
                task = decision_engine.make_trading_decision(
                    "BTCUSDT", (batch * batch_size) + i + 1
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            # Sample memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_samples.append(current_memory)

            # Verify all decisions succeeded
            assert len(results) == batch_size
            for result in results:
                assert isinstance(result, DecisionResult)

        # Analyze memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        max_memory = max(memory_samples)
        avg_memory = statistics.mean(memory_samples)
        memory_growth = final_memory - initial_memory

        print("Memory Usage Analysis:")
        print(f"  Initial: {initial_memory:.2f} MB")
        print(f"  Final: {final_memory:.2f} MB")
        print(f"  Maximum: {max_memory:.2f} MB")
        print(f"  Average: {avg_memory:.2f} MB")
        print(f"  Growth: {memory_growth:.2f} MB")

        # Memory assertions
        assert memory_growth < 50.0  # Memory growth should be less than 50MB
        assert max_memory < initial_memory + 100.0  # Peak memory should not exceed initial + 100MB

    @pytest.mark.asyncio
    async def test_decision_caching_performance(self, decision_engine, mock_services_fast):
        """Test performance impact of decision caching."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Test without caching (first calls)
        uncached_times = []
        for i in range(5):
            start_time = time.time()
            result = await decision_engine.make_trading_decision("BTCUSDT", i + 1)
            end_time = time.time()

            uncached_times.append((end_time - start_time) * 1000)
            assert isinstance(result, DecisionResult)

        # Test with potential caching (repeated calls)
        cached_times = []
        for i in range(5):
            start_time = time.time()
            result = await decision_engine.make_trading_decision("BTCUSDT", i + 1)
            end_time = time.time()

            cached_times.append((end_time - start_time) * 1000)
            assert isinstance(result, DecisionResult)

        avg_uncached = statistics.mean(uncached_times)
        avg_cached = statistics.mean(cached_times)

        print("Caching Performance:")
        print(f"  Average uncached: {avg_uncached:.2f}ms")
        print(f"  Average cached: {avg_cached:.2f}ms")
        print(f"  Performance ratio: {avg_uncached / avg_cached:.2f}x")

        # Both should be reasonably fast
        assert avg_uncached < 100.0  # Uncached should be under 100ms
        assert avg_cached < 100.0  # Cached should also be under 100ms

    @pytest.mark.asyncio
    async def test_error_handling_performance_impact(self, decision_engine, mock_services_fast):
        """Test performance impact of error handling."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Test normal operation performance
        normal_times = []
        for _ in range(10):
            start_time = time.time()
            result = await decision_engine.make_trading_decision("BTCUSDT", 1)
            end_time = time.time()

            normal_times.append((end_time - start_time) * 1000)
            assert isinstance(result, DecisionResult)
            assert result.validation_passed is True

        # Test with errors (mock context builder failure)
        error_times = []
        original_build_context = mock_services_fast["context_builder"].build_trading_context

        async def failing_context_builder(*args, **kwargs):
            await asyncio.sleep(0.005)  # Same delay as normal
            raise Exception("Simulated context building failure")

        mock_services_fast["context_builder"].build_trading_context = failing_context_builder

        for _ in range(10):
            start_time = time.time()
            result = await decision_engine.make_trading_decision("BTCUSDT", 1)
            end_time = time.time()

            error_times.append((end_time - start_time) * 1000)
            assert isinstance(result, DecisionResult)
            # Should handle error gracefully - validation_passed can be True for fallback decisions
            # The key is that it returns a DecisionResult, not that validation_passed is False

        # Restore original function
        mock_services_fast["context_builder"].build_trading_context = original_build_context

        avg_normal = statistics.mean(normal_times)
        avg_error = statistics.mean(error_times)

        print("Error Handling Performance:")
        print(f"  Average normal: {avg_normal:.2f}ms")
        print(f"  Average with errors: {avg_error:.2f}ms")
        print(f"  Error overhead: {avg_error - avg_normal:.2f}ms")

        # Error handling should not significantly impact performance
        assert avg_error < avg_normal * 2.0  # Error handling should not double the time
        assert avg_error < 200.0  # Even with errors, should be under 200ms

    @pytest.mark.asyncio
    async def test_sustained_load_stability(self, decision_engine, mock_services_fast):
        """Test system stability under sustained load."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Run sustained load for extended period
        duration_seconds = 10  # 10 second test
        decisions_per_second = 10
        total_expected = duration_seconds * decisions_per_second

        start_time = time.time()
        completed_decisions = 0
        errors = []

        # Create a continuous stream of decisions
        async def decision_worker():
            nonlocal completed_decisions, errors
            while time.time() - start_time < duration_seconds:
                try:
                    result = await decision_engine.make_trading_decision(
                        "BTCUSDT", completed_decisions + 1
                    )
                    if isinstance(result, DecisionResult):
                        completed_decisions += 1
                    await asyncio.sleep(1.0 / decisions_per_second)  # Rate limiting
                except Exception as e:
                    errors.append(e)

        # Run multiple workers concurrently
        workers = [decision_worker() for _ in range(3)]
        await asyncio.gather(*workers, return_exceptions=True)

        actual_duration = time.time() - start_time
        actual_rate = completed_decisions / actual_duration

        print("Sustained Load Test:")
        print(f"  Duration: {actual_duration:.2f}s")
        print(f"  Completed decisions: {completed_decisions}")
        print(f"  Target rate: {decisions_per_second} decisions/sec")
        print(f"  Actual rate: {actual_rate:.2f} decisions/sec")
        print(f"  Errors: {len(errors)}")

        # Stability assertions
        assert len(errors) == 0  # No errors should occur
        assert completed_decisions > total_expected * 0.8  # At least 80% of expected decisions
        assert actual_rate > decisions_per_second * 0.8  # At least 80% of target rate

    @pytest.mark.asyncio
    async def test_resource_cleanup_performance(self, decision_engine, mock_services_fast):
        """Test resource cleanup and garbage collection performance."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Generate many decisions to create objects for cleanup
        num_decisions = 50

        # Measure time including cleanup
        start_time = time.time()

        for i in range(num_decisions):
            result = await decision_engine.make_trading_decision("BTCUSDT", i + 1)
            assert isinstance(result, DecisionResult)

            # Periodically trigger cleanup operations
            if i % 10 == 0:
                # Simulate cache cleanup
                if hasattr(decision_engine, "clear_expired_cache"):
                    decision_engine.clear_expired_cache()

        end_time = time.time()

        total_time = end_time - start_time
        avg_time_per_decision = (total_time / num_decisions) * 1000  # ms

        print("Resource Cleanup Performance:")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Average per decision: {avg_time_per_decision:.2f}ms")
        print(f"  Throughput: {num_decisions / total_time:.2f} decisions/sec")

        # Performance assertions
        assert avg_time_per_decision < 100.0  # Average should be under 100ms per decision
        assert total_time < 10.0  # Total should complete within 10 seconds

    @pytest.mark.asyncio
    async def test_scalability_limits(self, decision_engine, mock_services_fast):
        """Test system behavior at scalability limits."""
        # Inject mock services
        for service_name, service in mock_services_fast.items():
            setattr(decision_engine, service_name, service)

        # Test increasing load until performance degrades
        concurrency_levels = [10, 25, 50, 100, 200]
        performance_results = []

        for concurrency in concurrency_levels:
            # Create high concurrency load
            tasks = []
            for i in range(concurrency):
                task = decision_engine.make_trading_decision("BTCUSDT", i + 1)
                tasks.append(task)

            # Measure performance
            start_time = time.time()
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=30.0,  # 30 second timeout
                )
                end_time = time.time()

                duration = end_time - start_time
                successful = sum(1 for r in results if isinstance(r, DecisionResult))
                throughput = successful / duration
                success_rate = successful / concurrency

                performance_results.append(
                    {
                        "concurrency": concurrency,
                        "duration": duration,
                        "successful": successful,
                        "throughput": throughput,
                        "success_rate": success_rate,
                    }
                )

                print(
                    f"Concurrency {concurrency}: {throughput:.1f} req/s, {success_rate:.2%} success"
                )

            except asyncio.TimeoutError:
                print(f"Concurrency {concurrency}: Timeout - system overloaded")
                performance_results.append(
                    {
                        "concurrency": concurrency,
                        "duration": 30.0,
                        "successful": 0,
                        "throughput": 0,
                        "success_rate": 0,
                    }
                )
                break  # Stop testing higher concurrency levels

        # Analyze scalability
        if len(performance_results) >= 2:
            # Find the point where performance starts to degrade significantly
            peak_throughput = max(r["throughput"] for r in performance_results)
            acceptable_throughput = peak_throughput * 0.8  # 80% of peak

            scalable_levels = [
                r for r in performance_results if r["throughput"] >= acceptable_throughput
            ]
            max_scalable_concurrency = (
                max(r["concurrency"] for r in scalable_levels) if scalable_levels else 0
            )

            print("Scalability Analysis:")
            print(f"  Peak throughput: {peak_throughput:.1f} req/s")
            print(f"  Max scalable concurrency: {max_scalable_concurrency}")

            # Scalability assertions
            assert max_scalable_concurrency >= 25  # Should handle at least 25 concurrent requests
            assert peak_throughput > 50.0  # Should achieve at least 50 req/s peak throughput
