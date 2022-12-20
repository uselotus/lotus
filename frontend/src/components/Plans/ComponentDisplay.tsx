import React, { FC } from "react";
import { Button, Row, Col, Descriptions, Table } from "antd";
import { Paper } from "../base/Paper";
import { EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { CreateComponent, Tier } from "../../types/plan-type";
import "./ComponentDisplay.css";
import { PricingUnit } from "../../types/pricing-unit-type";

const renderCost = (record: Tier, pricing_unit: PricingUnit) => {
  switch (record.type) {
    case "per_unit":
      return (
        <span>
          {pricing_unit.symbol}
          {record.cost_per_batch} per {record.metric_units_per_batch} Unit
        </span>
      );

    case "flat":
      return (
        <span>
          {pricing_unit.symbol}
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
  deleteComponent: (id: string) => void;
  pricing_unit: PricingUnit;
}> = ({
  componentsData,
  handleComponentEdit,
  deleteComponent,
  pricing_unit,
}) => {
  return (
    <Row gutter={[12, 12]} className="overflow-y-auto max-h-[400px]">
      {componentsData.map((component: any, index: number) => (
        <Col span="24" key={index}>
          <Paper border={true} className="items-stretch">
            <Descriptions
              title={component?.metric}
              className="text-[20px]"
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
                  render: (value: any, record: Tier) => (
                    <div>{renderCost(record, pricing_unit)}</div>
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
