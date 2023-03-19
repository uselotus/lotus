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

export const validate = async (form: FormInstance<any>, type?: string): Promise<boolean> => {
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
    </Row>
  );
};

export default PlanInformation;
