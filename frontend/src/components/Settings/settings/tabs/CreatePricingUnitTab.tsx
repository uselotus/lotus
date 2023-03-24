import { Button, Card, Col, Form, Input, Row } from "antd";
// @ts-ignore
import React from "react";
import { useMutation } from '@tanstack/react-query';
import { toast } from "react-toastify";
import { PricingUnits } from "../../../../api/api";
import { CurrencyType } from "../../../../types/pricing-unit-type";

function CreatePricingUnit() {
  const [form] = Form.useForm();
  const mutation = useMutation(
    (post: CurrencyType) => PricingUnits.create(post),
    {
      onSuccess: () => {
        toast.success("Successfully created Pricing Unit", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
      },
      onError: () => {
        toast.error("Failed to create Pricing Unit", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const submit = () => {
    form
      .validateFields()
      .then((values) => mutation.mutate(values))
      .catch((info) => {});
  };

  return (
    <div>
      <Form.Provider>
        <Form
          form={form}
          name="create_pricing_unit"
          initialValues={{
            code: "",
            name: "",
            symbol: "",
          }}
          onFinish={submit}
          autoComplete="off"
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign="left"
        >
          <Row gutter={[24, 24]}>
            <Col span={12}>
              <Row gutter={[24, 24]}>
                <Col span="24">
                  <Card title="Pricing Unit Information">
                    <Form.Item
                      label="Code"
                      rules={[
                        { required: true, message: "Please enter a code" },
                      ]}
                      name="code"
                    >
                      <Input placeholder="Ex: Code for your Unit" />
                    </Form.Item>
                    <Form.Item
                      label="Name"
                      rules={[
                        { required: true, message: "Please enter a name" },
                      ]}
                      name="name"
                    >
                      <Input placeholder="Ex: Name for your Unit" />
                    </Form.Item>
                    <Form.Item
                      label="Symbol"
                      rules={[
                        { required: true, message: "Please enter a symbol" },
                      ]}
                      name="symbol"
                    >
                      <Input placeholder="Ex: Symbol for your Unit" />
                    </Form.Item>
                    <Form.Item>
                      <Button htmlType="submit">Create Unit</Button>
                    </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>
          </Row>
        </Form>
      </Form.Provider>
    </div>
  );
}

export default CreatePricingUnit;
