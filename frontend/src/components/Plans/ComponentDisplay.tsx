import React, { FC } from "react";
import {
  Button,
  Row,
  Col,
  Descriptions,
  Table,
  Typography,
  Divider,
} from "antd";
import { EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { Paper } from "../base/Paper";
import { CreateComponent, Tier } from "../../types/plan-type";
import "./ComponentDisplay.css";
import { CurrencyType } from "../../types/pricing-unit-type";
import clsx from "clsx";

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

interface Props {
  componentsData: CreateComponent[];
  handleComponentEdit: (id: string) => void;
  deleteComponent: (id: string) => void;
  pricing_unit: CurrencyType;
}

export const ComponentDisplay = ({ ...props }: Props) => (
  <div className={clsx(["grid grid-cols-1 gap-6 xl:grid-cols-4"])}>
    {props.componentsData.map((component) => (
      <div
        key={component.id}
        className={clsx([
          "pt-2 pb-4 px-4 my-2",
          "bg-primary-50",
          "min-h-[152px]",
        ])}
      >
        <div className="flex items-center justify-between">
          <Typography.Title
            className="pt-4 whitespace-pre-wrap !text-[18px]"
            level={2}
          >
            {component?.metric}
          </Typography.Title>
          <div className="flex items-center justify-end">
            <Button
              key="edit"
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => props.handleComponentEdit(component.metric_id)}
            />

            <Button
              key="delete"
              type="text"
              size="small"
              icon={<DeleteOutlined />}
              danger
              onClick={() => props.deleteComponent(component.metric_id)}
            />
          </div>
        </div>

        <Divider
          style={{
            marginBlock: "4px",
          }}
        />

        <div className="text-base text-card-text">
          {React.Children.toArray(
            component.tiers.map((tier) => (
              <div className="flex items-center justify-between">
                <div>
                  From {tier.range_start} to{" "}
                  {tier.range_end == null ? "∞" : tier.range_end}
                </div>
                <div>{renderCost(tier, props.pricing_unit)}</div>
              </div>
            ))
          )}
        </div>
      </div>
    ))}
  </div>
);

export default ComponentDisplay;
