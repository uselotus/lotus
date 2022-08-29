import React, { useEffect, useState } from "react";
import { RevenueType } from "../types/revenue-type";
import { GetRevenue } from "../api/api";
import { Button, Form, Input, InputNumber, Modal, Radio, Select } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";

const { Option } = Select;

function UsageComponentForm(props: { visible: boolean; onCancel: () => void }) {
  const [form] = Form.useForm();

  return (
    <Modal
      visible={props.visible}
      title="Add A Usage Pricing Component"
      okText="Create"
      okType="default"
      cancelText="Cancel"
      onCancel={props.onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            form.resetFields();
          })
          .catch((info) => {
            console.log("Validate Failed:", info);
          });
      }}
    >
      <Form
        form={form}
        layout="vertical"
        name="form_in_modal"
        initialValues={{ modifier: "public" }}
      >
        <Form.Item
          name="metric"
          label="Metric"
          rules={[
            {
              required: true,
              message: "Please select a metric",
            },
          ]}
        >
          <Select>
            <Option value="test-runs">Test-Runs</Option>
          </Select>
        </Form.Item>
        <Form.Item name="cost" label="Cost Per Unit Amount">
          <InputNumber addonBefore="$" defaultValue={0.0} precision={2} />
          <InputNumber addonBefore="per" defaultValue={1} precision={0} />
        </Form.Item>
        <Form.Item name="free-amount" label="Free Units">
          <InputNumber defaultValue={0} precision={0} />
        </Form.Item>
        <Form.Item
          name="aggregation_type"
          label="Aggregation Type"
          rules={[
            {
              required: true,
              message: "Please select an aggregation type",
            },
          ]}
        >
          <Select>
            <Option value="count">Count</Option>
            <Option value="sum">Sum</Option>
            <Option value="max">Max</Option>
          </Select>
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default UsageComponentForm;
