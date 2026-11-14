-- Logistics Platform Foreign Key and Integrity Constraints

ALTER TABLE routes ADD CONSTRAINT fk_route_orig FOREIGN KEY (origin_facility_id) REFERENCES facilities(facility_id);
ALTER TABLE routes ADD CONSTRAINT fk_route_dest FOREIGN KEY (destination_facility_id) REFERENCES facilities(facility_id);
ALTER TABLE carrier_calendars ADD CONSTRAINT fk_ccal_carrier FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id);
ALTER TABLE facility_calendars ADD CONSTRAINT fk_fcal_facility FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE shipments ADD CONSTRAINT fk_ship_carrier FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id);
ALTER TABLE shipments ADD CONSTRAINT fk_ship_orig FOREIGN KEY (origin_facility_id) REFERENCES facilities(facility_id);
ALTER TABLE shipments ADD CONSTRAINT fk_ship_dest FOREIGN KEY (destination_facility_id) REFERENCES facilities(facility_id);
ALTER TABLE shipment_legs ADD CONSTRAINT fk_leg_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id);
ALTER TABLE shipment_legs ADD CONSTRAINT fk_leg_orig FOREIGN KEY (origin_facility_id) REFERENCES facilities(facility_id);
ALTER TABLE shipment_legs ADD CONSTRAINT fk_leg_dest FOREIGN KEY (destination_facility_id) REFERENCES facilities(facility_id);
ALTER TABLE tracking_events ADD CONSTRAINT fk_evt_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id);
ALTER TABLE facility_queues ADD CONSTRAINT fk_queue_facility FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE disruptions ADD CONSTRAINT fk_disruption_facility FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE weather_events ADD CONSTRAINT fk_weather_facility FOREIGN KEY (facility_id) REFERENCES facilities(facility_id);
ALTER TABLE eta_estimates ADD CONSTRAINT fk_eta_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id);
ALTER TABLE shipment_status_history ADD CONSTRAINT fk_ssh_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id);
ALTER TABLE route_change_history ADD CONSTRAINT fk_rch_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id);
ALTER TABLE shipment_delay_reasons ADD CONSTRAINT fk_sdr_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id);
ALTER TABLE shipment_delay_reasons ADD CONSTRAINT fk_sdr_reason FOREIGN KEY (reason_id) REFERENCES delay_reasons(reason_id);