import {Modal, Tag} from "antd";
import {MetricType} from "../../types/metric-type";
// @ts-ignore
import React, {FC, Fragment} from "react";
import {colorMap} from "./MetricTable";

interface MetricDetailsProps {
    metric: MetricType;
    onclose: () => void;
}

const metricTypeColorMap = new Map<string, string>([
    ["counter", "green"],
    ["stateful", "blue"],
    ["rate", "purple"],
]);

const eventTypeColorMap = new Map<string, string>([
    ["delta", "green"],
    ["total", "blue"],
]);


const MetricDetails: FC<MetricDetailsProps> = ({metric, onclose}) => {
    return (
        <Modal
            visible
            title={<b> {metric?.billable_metric_name ? metric.billable_metric_name : "Metric"} Details</b>}
            cancelText="Close"
            width={800}
            onCancel={onclose}
            onOk={onclose}
        >
            <div
                className="py-4 flex items-start justify-between  px-8 rounded-lg bg-[#FFFFFF]  border-2 border-solid rounded border-[#EAEAEB]">
                <div>
                    <p><b className="mr-2">Id:</b> {metric.id ? metric.id : "N/A"}</p>
                    <p><b className="mr-2">Event Name:</b> {metric.event_name}</p>
                    <p><b className="mr-2">Property Name:</b> {metric.property_name}</p>
                    <p><b className="mr-2">Billable Metric
                        Name:</b> {metric.billable_metric_name ? metric.billable_metric_name : "N/A"}</p>
                    <p><b className="mr-2">Granularity:</b> {metric.granularity ? metric.granularity : "N/A"}</p>
                </div>
                <div>
                    <p><b className="mr-2">Usage Aggregation Type:</b>
                        <Tag color={colorMap.get(metric.usage_aggregation_type)}>
                            {metric.usage_aggregation_type}
                        </Tag>
                    </p>
                    <p><b className="mr-2">Billable Aggregation Type:</b>
                        {!!metric.billable_aggregation_type ?
                            (
                                <Tag color="yellow">
                                    {metric.billable_aggregation_type}
                                </Tag>
                            ) : "N/A"
                        }
                    </p>
                    <p><b className="mr-2">Metric Type:</b>
                        <Tag color={metricTypeColorMap.get(metric.metric_type)}>
                            {metric.metric_type}
                        </Tag>
                    </p>
                    <p><b className="mr-2">Event Type:</b>
                        {!!metric.event_type ?
                            (
                                <Tag color={eventTypeColorMap.get(metric.event_type)}>
                                    {metric.event_type}
                                </Tag>
                            ) : "N/A"
                        }
                    </p>
                </div>
            </div>
        </Modal>
    );
};

export default MetricDetails;
