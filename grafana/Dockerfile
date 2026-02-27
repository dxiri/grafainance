FROM grafana/grafana:12.3.3

USER root

# Copy provisioning files into the image
COPY provisioning/datasources /etc/grafana/provisioning/datasources
COPY provisioning/dashboards /etc/grafana/provisioning/dashboards

# Copy initialization script
COPY init-dashboards.sh /init-dashboards.sh
RUN chmod +x /init-dashboards.sh

# Make provisioning directories writable for init script
RUN chown -R grafana:root /etc/grafana/provisioning

# Switch back to grafana user
USER grafana

# Use our init script as entrypoint
ENTRYPOINT ["/init-dashboards.sh"]
