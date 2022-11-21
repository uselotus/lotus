import React, { FC } from "react";
import { Button, Row, Col, Descriptions, Table } from "antd";
import { Paper } from "../base/Paper";
import { EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { CreateComponent, Tier } from "../../types/plan-type";
import "./ComponentDisplay.css";

const dummy_components: CreateComponent[] = [
  {
    billable_metric_name: "API calls",
    tiers: [
      {
        cost_per_batch: 0.01,
        metric_units_per_batch: 1000,
        type: "per_unit",
        range_start: 0,
        range_end: 100000,
      },
    ],
  },
];

const renderCost = (record: Tier) => {
  switch (record.type) {
    case "per_unit":
      return (
        <span>
          {"$"}
          {record.cost_per_batch} per {record.metric_units_per_batch} Unit
        </span>
      );

    case "flat":
      return (
        <span>
          {"$"}
          {record.cost_per_batch}{" "}
        </span>
      );

    case "free":
      return <span>{"Free"}</span>;
  }
};
//standard react component FC with props {componentsData}
export const ComponentDisplay: FC<{
  componentsData: CreateComponent[];
  handleComponentEdit: (any) => void;
  deleteComponent: (any) => void;
}> = ({ componentsData, handleComponentEdit, deleteComponent }) => {
  return (
    <Row gutter={[12, 12]}>
      {componentsData.map((component: any, index: number) => (
        <Col span="24" key={index}>
          <Paper>
            <Descriptions
              title={component?.metric}
              size="small"
              column={2}
              extra={[
                <Button
                  key="edit"
                  type="text"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => handleComponentEdit(component.id)}
                />,
                <Button
                  key="delete"
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  danger
                  onClick={() => deleteComponent(component.id)}
                />,
              ]}
            ></Descriptions>
            <Table
              dataSource={component.tiers}
              pagination={false}
              showHeader={false}
              style={{ backgroundColor: "FAFAFA" }}
              size="middle"
              rowClassName="bg-[#FAFAFA]"
              className="noborderTable"
              columns={[
                {
                  title: "Range",
                  dataIndex: "range_start",
                  key: "range_start",
                  align: "left",
                  width: "50%",
                  render: (value: any, record: any) => (
                    <span>
                      From {value} to{" "}
                      {record.range_end == null ? "∞" : record.range_end}
                    </span>
                  ),
                },
                {
                  title: "Cost",
                  align: "left",
                  dataIndex: "cost_per_batch",
                  key: "cost_per_batch",
                  render: (value: any, record: any) => (
                    <div>{renderCost(record)}</div>
                  ),
                },
              ]}
            />
          </Paper>
        </Col>
      ))}
    </Row>
  );
};

export default ComponentDisplay;
