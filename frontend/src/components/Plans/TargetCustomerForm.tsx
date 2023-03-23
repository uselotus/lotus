import React, { useState } from "react";
import { Form, Modal, Select } from "antd";
import { UseQueryResult, useQuery } from '@tanstack/react-query';
import { Customer } from "../../api/api";
import { CustomerPlus } from "../../types/customer-type";

const { Option } = Select;

interface Props {
  visible: boolean;
  onCancel: () => void;
  onAddTargetCustomer: (target_customer_id: string) => void;
}

function TargetCustomerForm({ ...props }: Props) {
  const [form] = Form.useForm();
  const [targetCustomer, setTargetCustomer] = useState<string>(""); // id of the target customer

  const { data: customers }: UseQueryResult<CustomerPlus[]> = useQuery<
    CustomerPlus[]
  >(["customer_list"], () => Customer.getCustomers().then((res) => res));

  return (
    <Form.Provider>
      <Form
        form={form}
        name="target_customer_form"
        layout="vertical"
        initialValues={{
          target_customer: targetCustomer,
        }}
        onFinish={() => {
          props.onAddTargetCustomer(targetCustomer);
        }}
      >
        <Modal
          visible={props.visible}
          title="Choose Target Customer For Plan"
          okText="Confirm and Create Plan"
          okType="default"
          okButtonProps={{
            type: "primary",
          }}
          onCancel={props.onCancel}
          onOk={() => {
            form.submit();
          }}
        >
          <div className="grid grid-row-3">
            <div className="flex flex-col">
              <Form.Item
                name="target_customer"
                label="Customer"
                rules={[{ required: true }]}
              >
                <Select
                  placeholder="Choose Customer"
                  showSearch
                  onChange={(value) => {
                    setTargetCustomer(value);
                  }} // id of the target customer)}
                >
                  {React.Children.toArray(
                    customers?.map((customer) => (
                      <Option value={customer.customer_id}>
                        {customer.customer_name}
                      </Option>
                    ))
                  )}
                </Select>
              </Form.Item>
            </div>
          </div>
        </Modal>
      </Form>
    </Form.Provider>
  );
}

export default TargetCustomerForm;
