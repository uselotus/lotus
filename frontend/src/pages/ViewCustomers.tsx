import React, { FC, useState } from "react";
import { PlusOutlined } from "@ant-design/icons";
import { Button } from "antd";
import {
  useQuery,
  UseQueryResult,
  useQueryClient,
  useMutation,
} from "react-query";
import { toast } from "react-toastify";
import CustomerTable from "../components/Customers/CustomerTable";
import {
  CustomerTotal,
  CustomerCreateType,
  CustomerSummary,
} from "../types/customer-type";
import { Customer } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { PageLayout } from "../components/base/PageLayout";
import CreateCustomerForm, {
  CreateCustomerState,
} from "../components/Customers/CreateCustomerForm";

const ViewCustomers: FC = () => {
  const queryClient = useQueryClient();
  const [visible, setVisible] = useState(false);

  const { data, isLoading }: UseQueryResult<CustomerSummary[]> = useQuery<
    CustomerSummary[]
  >(["customer_list"], () => Customer.getCustomers().then((res) => res));
  const { data: customerTotals } = useQuery<CustomerTotal[]>(
    ["customer_totals"],
    () => Customer.getCustomerTotals().then((res) => res)
  );

  const mutation = useMutation(
    (post: CustomerCreateType) => Customer.createCustomer(post),
    {
      onSuccess: () => {
        setVisible(false);
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_totals"]);
        toast.success("Customer created successfully", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Error creating customer", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const openCustomerModal = () => {
    setVisible(true);
  };

  const onCancel = () => {
    setVisible(false);
  };

  const onSave = (state: CreateCustomerState) => {
    const customerInstance: CustomerCreateType = {
      customer_id: state.customer_id,
      customer_name: state.name,
      email: state.email,
    };
    if (state.payment_provider) {
      customerInstance.payment_provider = state.payment_provider;
      customerInstance.payment_provider_id = state.payment_provider_id;
    }
    if (state.default_currency_code) {
      customerInstance.default_currency_code = state.default_currency_code;
    }

    mutation.mutate(customerInstance);
    onCancel();
  };

  return (
    <PageLayout
      title="Customers"
      extra={[
        <Button
          onClick={openCustomerModal}
          type="primary"
          size="large"
          key="create-plan"
          className="hover:!bg-primary-700"
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
        >
          <div className="flex items-center  justify-between text-white">
            <div>
              <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
              Create Customer
            </div>
          </div>
        </Button>,
      ]}
    >
      <div>
        {isLoading || data === undefined ? (
          <LoadingSpinner />
        ) : (
          <CustomerTable customerArray={data} totals={customerTotals} />
        )}
        <CreateCustomerForm
          visible={visible}
          onSave={onSave}
          onCancel={onCancel}
        />
      </div>
    </PageLayout>
  );
};

export default ViewCustomers;
