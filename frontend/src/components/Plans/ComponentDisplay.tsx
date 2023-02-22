import React, { FC } from "react";
import { Button, Row, Col, Descriptions, Table } from "antd";
import { EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { Paper } from "../base/Paper";
import { CreateComponent, Tier } from "../../types/plan-type";
import "./ComponentDisplay.css";
import { CurrencyType } from "../../types/pricing-unit-type";

const returnRoundingText = (rounding: string | undefined) => {
  if (!rounding) {
    return "";
  }
  switch (rounding) {
    case "round_down":
      return "Round Down";
    case "round_up":
      return "Round Up";
    case "round_nearest":
      return "Round Nearest";
    case "no_rounding":
      return "No Rounding";
    default:
      return "No Rounding";
  }
};

const renderCost = (record: Tier, pricing_unit: CurrencyType) => {
  switch (record.type) {
    case "per_unit":
      return (
        <span>
          {pricing_unit.symbol}
          {record.cost_per_batch} per {record.metric_units_per_batch} Unit
          {record.metric_units_per_batch > 1 ? "s " : " "}(
          {returnRoundingText(record.batch_rounding_type)})
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
      return <span>Free</span>;
  }
};
// standard react component FC with props {componentsData}
export const ComponentDisplay: FC<{
  componentsData: CreateComponent[];
  handleComponentEdit: (any) => void;
  deleteComponent: (id: string) => void;
  pricing_unit: CurrencyType;
}> = ({
  componentsData,
  handleComponentEdit,
  deleteComponent,
  pricing_unit,
}) => (
  <Row gutter={[12, 12]} className="overflow-y-auto max-h-[400px]">
    {componentsData.map((component) => (
      <Col span="24" key={component.id}>
        <Paper border className="items-stretch">
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
          />
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

export default ComponentDisplay;
