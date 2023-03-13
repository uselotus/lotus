import React from "react";
import moment from "moment";
import {
  Row,
  Card,
  Col,
  Input,
  InputNumber,
  Select,
  Form,
  Radio,
  FormInstance,
} from "antd";
import { StepProps } from "./types";
import LinkExternalIds from "../LinkExternalIds";

const fields = ["name", "plan_duration"];

export const validate = async (form: FormInstance<any>): Promise<boolean> => {
  try {
    await form.validateFields(fields);
    return true;
  } catch (err) {
    return false;
  }
};

const PlanInformation = ({ form, ...props }: StepProps) => {
  React.useEffect(() => {
    const isValid = fields.every((field) => form.getFieldValue(field));

    props.setIsCurrentStepValid(isValid);
  }, [form, props]);

  return (
    <Row gutter={[24, 24]}>
      <Col span={24}>
        <Row gutter={[24, 24]}>
          <Col span="24">
            <Card title="Plan Information" className="w-full">
              <Input.Group>
                <Row gutter={[24, 24]}>
                  <Col span={12}>
                    <Form.Item
                      label="Plan Name"
                      name="name"
                      rules={[
                        {
                          required: true,
                          message: "Please Name Your Plan",
                        },
                      ]}
                    >
                      <Input
                        disabled={props.disabledFields?.includes("name")}
                        id="planNameInput"
                        placeholder="Ex: Starter Plan"
                      />
                    </Form.Item>
                  </Col>

                  <Col span={12}>
                    <Form.Item label="Description" name="description">
                      <Input
                        disabled={props.disabledFields?.includes("description")}
                        type="textarea"
                        id="planDescInput"
                        placeholder="Ex: Cheapest plan for small scale businesses"
                      />
                    </Form.Item>
                  </Col>

                  <Col span={12}>
                    <Form.Item
                      name="initial_external_links"
                      label="Link External IDs"
                    >
                      <LinkExternalIds
                        externalIds={[]}
                        setExternalLinks={props.setExternalLinks}
                      />
                    </Form.Item>
                  </Col>

                  <Col span="12">
                    <Form.Item
                      label="Duration"
                      name="plan_duration"
                      rules={[
                        {
                          required: true,
                          message: "Please select a duration",
                        },
                      ]}
                    >
                      <Radio.Group
                        disabled={props.disabledFields?.includes("plan_duration")}
                        onChange={(e) => {
                          if (e.target.value === "monthly") {
                            props.setAvailableBillingTypes([
                              { label: "Monthly", name: "monthly" },
                            ]);
                            form.setFieldValue(
                              "usage_billing_frequency",
                              "monthly"
                            );
                          } else if (e.target.value === "quarterly") {
                            props.setAvailableBillingTypes([
                              { label: "Monthly", name: "monthly" },
                              { label: "Quarterly", name: "quarterly" },
                            ]);
                            form.setFieldValue(
                              "usage_billing_frequency",
                              "quarterly"
                            );
                          } else {
                            props.setAvailableBillingTypes([
                              { label: "Monthly", name: "monthly" },
                              { label: "Quarterly", name: "quarterly" },
                              { label: "Yearly", name: "yearly" },
                            ]);
                            form.setFieldValue(
                              "usage_billing_frequency",
                              "yearly"
                            );
                          }
                        }}
                      >
                        <Radio value="monthly">Monthly</Radio>
                        <Radio value="quarterly">Quarterly</Radio>
                        <Radio value="yearly">Yearly</Radio>
                      </Radio.Group>
                    </Form.Item>
                  </Col>
                </Row>
              </Input.Group>
            </Card>
          </Col>
        </Row>
      </Col>

      <Col span="24">
        <Card
          className="w-12/12 mb-20"
          title="Discount"
          style={{
            borderRadius: "0.5rem",
            borderWidth: "2px",
            borderColor: "#EAEAEB",
            borderStyle: "solid",
          }}
        >
          <div className="grid grid-cols-2">
            <Form.Item
              wrapperCol={{ span: 20 }}
              label="Type"
              name="price_adjustment_type"
            >
              <Select
                onChange={(value) => {
                  props.setPriceAdjustmentType(value);
                }}
              >
                <Select.Option value="none">None</Select.Option>
                {/* <Select.Option value="price_override">
                        Overwrite Price
                      </Select.Option> */}
                <Select.Option value="percentage">Percentage Off</Select.Option>
                <Select.Option value="fixed">Flat Discount</Select.Option>
              </Select>
            </Form.Item>

            {props.priceAdjustmentType !== "none" && (
              <Form.Item
                name="price_adjustment_amount"
                label="Amount"
                wrapperCol={{ span: 24, offset: 4 }}
                shouldUpdate={(prevValues, curValues) =>
                  prevValues.price_adjustment_type !==
                  curValues.price_adjustment_type
                }
                rules={[
                  {
                    required:
                      !!props.priceAdjustmentType ||
                      props.priceAdjustmentType !== "none",
                    message: "Please enter a price adjustment value",
                  },
                ]}
              >
                <InputNumber
                  addonAfter={
                    props.priceAdjustmentType === "percentage" ? "%" : null
                  }
                  addonBefore={
                    (props.priceAdjustmentType === "fixed" ||
                      props.priceAdjustmentType === "price_override") &&
                    props.selectedCurrency
                      ? props.selectedCurrency.symbol
                      : null
                  }
                />
              </Form.Item>
            )}
          </div>
        </Card>
      </Col>
    </Row>
  );
};

export default PlanInformation;
