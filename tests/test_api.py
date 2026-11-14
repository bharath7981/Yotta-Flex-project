"""Integration Tests for API Endpoints"""
import pytest
from app.dependencies import get_cached_data, get_predictor, get_repository
from src.api.routes.health import health_check
from src.api.routes.dashboard import get_dashboard_summary, get_carrier_performance
from src.api.routes.shipments import list_shipments, get_shipment_detail
from src.api.routes.predictions import predict_eta, predict_delay_risk, ETAPredictionRequest


@pytest.fixture(scope="module")
def data():
    return get_cached_data()


@pytest.fixture(scope="module")
def predictor():
    return get_predictor()


def test_health_endpoint():
    res = health_check()
    assert res["status"] == "healthy"


def test_dashboard_summary(data):
    summary = get_dashboard_summary(data)
    assert summary.total_shipments >= 500
    assert summary.delivered_shipments > 0
    assert summary.on_time_delivery_pct > 0.0


def test_shipments_endpoints(data):
    res = list_shipments(skip=0, limit=10, data=data)
    assert res.total >= 500
    assert len(res.shipments) == 10

    first_id = res.shipments[0].shipment_id
    single = get_shipment_detail(first_id, data=data)
    assert single.shipment_id == first_id


def test_predictions_endpoint(data, predictor):
    first_id = data["shipments"].iloc[0]["shipment_id"]
    req = ETAPredictionRequest(shipment_id=first_id)
    eta_res = predict_eta(req, data=data, predictor=predictor)
    assert eta_res.predicted_remaining_hours >= 0.0

    risk_res = predict_delay_risk(req, data=data, predictor=predictor)
    assert 0.0 <= risk_res.delay_probability <= 1.0


def test_shipment_sub_resources(data):
    from src.api.routes.shipments import get_shipment_legs, get_shipment_events, get_shipment_delay_reasons, get_shipment_eta_history
    ship_id = data["shipments"].iloc[0]["shipment_id"]
    
    legs = get_shipment_legs(ship_id, data=data)
    assert isinstance(legs, list)
    assert len(legs) > 0
    
    events = get_shipment_events(ship_id, data=data)
    assert isinstance(events, list)
    assert len(events) > 0

    eta_history = get_shipment_eta_history(ship_id, data=data)
    assert isinstance(eta_history, list)


def test_carriers_endpoint(data):
    from src.api.routes.carriers import list_carriers, get_carrier
    res = list_carriers(data=data)
    assert res.total >= 8
    first_id = res.carriers[0].carrier_id
    single = get_carrier(first_id, data=data)
    assert single.carrier_id == first_id


def test_facilities_and_queues(data):
    from src.api.routes.facilities import list_facilities, get_facility, get_facility_queues
    res = list_facilities(data=data)
    assert res.total >= 15
    first_id = res.facilities[0].facility_id
    single = get_facility(first_id, data=data)
    assert single.facility_id == first_id
    
    queues = get_facility_queues(first_id, data=data)
    assert queues.facility_id == first_id


def test_routes_endpoint(data):
    from src.api.routes.routes_api import list_routes, get_route
    res = list_routes(data=data)
    assert res.total > 0
    first_id = res.routes[0].route_id
    single = get_route(first_id, data=data)
    assert single.route_id == first_id


def test_weather_endpoint(data):
    from src.api.routes.weather import list_weather_events
    res = list_weather_events(data=data)
    assert res.total >= 40


def test_analytics_and_validation(data):
    from src.api.routes.analytics import get_eta_performance, get_delay_performance, get_analytics_anomalies
    from src.api.routes.validation import get_validation_summary
    
    eta_perf = get_eta_performance(data=data)
    assert "mae_hours" in eta_perf
    
    delay_perf = get_delay_performance(data=data)
    assert "overall_delay_rate" in delay_perf
    
    anoms = get_analytics_anomalies(data=data)
    assert anoms.total_detected >= 0
    
    val = get_validation_summary(data=data)
    assert val["status"] in ["PASSED", "FAILED"]


def test_missing_shipment_404(data):
    from fastapi import HTTPException
    from src.api.routes.shipments import get_shipment_detail
    with pytest.raises(HTTPException) as exc:
        get_shipment_detail("SHP-NON-EXISTENT", data=data)
    assert exc.value.status_code == 404


def test_missing_carrier_404(data):
    from fastapi import HTTPException
    from src.api.routes.carriers import get_carrier
    with pytest.raises(HTTPException) as exc:
        get_carrier("CAR-NON-EXISTENT", data=data)
    assert exc.value.status_code == 404


def test_missing_facility_404(data):
    from fastapi import HTTPException
    from src.api.routes.facilities import get_facility
    with pytest.raises(HTTPException) as exc:
        get_facility("FAC-NON-EXISTENT", data=data)
    assert exc.value.status_code == 404


def test_missing_route_404(data):
    from fastapi import HTTPException
    from src.api.routes.routes_api import get_route
    with pytest.raises(HTTPException) as exc:
        get_route("RTE-NON-EXISTENT", data=data)
    assert exc.value.status_code == 404


def test_prediction_missing_shipment_404(data, predictor):
    from fastapi import HTTPException
    from src.api.routes.predictions import predict_eta, ETAPredictionRequest
    with pytest.raises(HTTPException) as exc:
        predict_eta(ETAPredictionRequest(shipment_id="SHP-NON-EXISTENT"), data=data, predictor=predictor)
    assert exc.value.status_code == 404


