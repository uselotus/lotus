import React, { FC, useState, useEffect, useRef } from "react";
import {
  DownOutlined,
  EllipsisOutlined,
  QuestionCircleOutlined,
  DeleteOutlined,
  DeleteFilled,
} from "@ant-design/icons";
import {
  ProTable,
  ProFormInstance,
  ProColumns,
} from "@ant-design/pro-components";
import { Table } from "antd";
import { CustomerTableItem } from "../types/customer-type";
import { Button, Tag, Tooltip } from "antd";
import { PlanDisplay } from "../types/plan-type";
import { useNavigate } from "react-router-dom";
import { MetricType } from "../types/metric-type";
import { Metrics } from "../api/api";

const colorMap = new Map<string, string>([
  ["count", "green"],
  ["sum", "blue"],
  ["max", "pink"],
]);

interface Props {
  metricArray: MetricType[];
}

const MetricTable: FC<Props> = ({ metricArray }) => {
  const navigate = useNavigate();
  const formRef = useRef<ProFormInstance>();

  const columns: ProColumns<MetricType>[] = [
    {
      title: "Metric Name",
      width: 200,
      dataIndex: "billable_metric_name",
      align: "left",
    },
    {
      title: "Event Name",
      width: 120,
      dataIndex: "event_name",
      align: "left",
    },
    {
      title: "Aggregation Type",
      width: 120,
      dataIndex: "aggregation_type",
      render: (_, record) => (
        <Tag color={colorMap.get(record.aggregation_type)}>
          {record.aggregation_type}
        </Tag>
      ),
    },
    {
      title: "Property Name",
      width: 120,
      dataIndex: "property_name",
      align: "left",
    },
    // {
    //   title: "Actions",
    //   align: "right",
    //   valueType: "option",
    //   render: (_, record) => [
    //     <a
    //       key="delete"
    //       onClick={() => {
    //         const tableDataSource = formRef.current?.getFieldValue(
    //           "table"
    //         ) as MetricType[];
    //         formRef.current?.setFieldsValue({
    //           table: tableDataSource.filter((item) => item.id !== record?.id),
    //         });
    //       }}
    //     >
    //       <DeleteOutlined />
    //     </a>,
    //   ],
    // },
  ];

  const handleDelete = (id: number) => {
    Metrics.deleteMetric(id).then((res) => {});
  };

  const navigateCreateCustomer = () => {
    navigate("/customers/create");
  };
  return (
    <React.Fragment>
      <ProTable<MetricType>
        columns={columns}
        dataSource={metricArray}
        rowKey="customer_id"
        formRef={formRef}
        search={false}
        pagination={{
          showTotal: (total, range) => (
            <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
          ),
        }}
        options={false}
      />
    </React.Fragment>
  );
};

export default MetricTable;
